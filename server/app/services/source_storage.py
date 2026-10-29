"""Private DB persistence. Callers must authorize the template before resolving it."""
import re
import tempfile
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import object_session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import StoredFile

PREFIX = "dbfile://"
KEY = re.compile(r"^[a-f0-9]{32}\.(docx|pdf|hwpx)$")
request_files = ContextVar("request_files", default=None)


def track(path):
    files = request_files.get()
    if files is not None:
        files.append(path)
    return path


class TemporaryFilesMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        files = []
        from app.core.render_security import seal_authorized
        seal_token = seal_authorized.set(False)
        token = request_files.set(files)
        try:
            await self.app(scope, receive, send)
        finally:
            for path in files:
                path.unlink(missing_ok=True)
            request_files.reset(token)
            seal_authorized.reset(seal_token)


def persist(db, path, user_id):
    if not settings.CLOUD_MODE:
        from app.core.encryption import encrypt
        path.write_bytes(encrypt(path.read_bytes()))
        sidecar = path.with_suffix('.hwpx')
        if path.suffix == '.hwp' and sidecar.exists():
            sidecar.write_bytes(encrypt(sidecar.read_bytes()))
        return str(path)
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(73904121)"))
    total = db.scalar(select(func.coalesce(func.sum(func.length(StoredFile.data)), 0)))
    own = db.scalar(select(func.count()).select_from(StoredFile).where(StoredFile.owner_id == user_id))
    data = path.read_bytes()
    if total + len(data) > 100 * 1024 * 1024 or own >= 20:
        raise HTTPException(413, "무료 체험 저장 한도입니다. 사용하지 않는 업로드 양식을 삭제한 뒤 다시 시도하세요.")
    db.add(StoredFile(key=path.name, owner_id=user_id, data=data))
    return PREFIX + path.name


def resolve(template):
    source = template.source_path
    if template.expires_at and template.expires_at < datetime.utcnow():
        raise HTTPException(410, "원본 보관기간이 만료되었습니다. 양식을 다시 업로드하세요.")
    if not source:
        return None
    if not source.startswith(PREFIX):
        from app.core.encryption import PREFIX as ENC_PREFIX, decrypt
        path = Path(source)
        if not path.exists():
            return path
        data = path.read_bytes()
        if not data.startswith(ENC_PREFIX):
            return path
        with tempfile.NamedTemporaryFile(dir=settings.UPLOAD_DIR, suffix=path.suffix, delete=False) as f:
            f.write(decrypt(data))
            result = track(Path(f.name))
        sidecar = path.with_suffix('.hwpx')
        if path.suffix == '.hwp' and sidecar.exists():
            derived = result.with_suffix('.hwpx')
            derived.write_bytes(decrypt(sidecar.read_bytes()))
            track(derived)
        return result
    key = source[len(PREFIX):]
    if not KEY.fullmatch(key):
        raise HTTPException(409, "원본 파일 식별자가 올바르지 않습니다.")
    session = object_session(template)
    if session is not None:
        row = session.get(StoredFile, key)
        data = bytes(row.data) if row else None
    else:
        with SessionLocal() as db:
            row = db.get(StoredFile, key)
            data = bytes(row.data) if row else None
    if data is None:
        raise HTTPException(410, "원본 파일이 삭제되었습니다. 다시 업로드하세요.")
    if row.owner_id != template.owner_id and template.owner_id is not None:
        raise HTTPException(404, "원본 파일을 찾을 수 없습니다.")
    with tempfile.NamedTemporaryFile(dir=settings.UPLOAD_DIR, suffix=Path(key).suffix, delete=False) as f:
        f.write(data)
        return track(Path(f.name))


def remove(db, template):
    if not template.source_path:
        return
    if template.source_path.startswith(PREFIX):
        row = db.get(StoredFile, template.source_path[len(PREFIX):])
        if row:
            db.delete(row)
    else:
        path = Path(template.source_path)
        path.unlink(missing_ok=True)
        if template.source_type == "hwp":
            path.with_suffix(".hwpx").unlink(missing_ok=True)
