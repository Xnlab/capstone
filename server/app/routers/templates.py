import uuid
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models import AuditLog, Document, Template, User
from app.schemas import TemplateMappingIn
from app.services import ai, form_parser
from app.services.documents import template_keys
from app.standard_fields import STANDARD_FIELDS

router = APIRouter(prefix="/templates", tags=["templates"])


def to_out(t: Template) -> dict:
    return {
        "id": t.id, "kind": t.kind, "name": t.name, "category": t.category,
        "description": t.description, "aliases": t.aliases or [], "fields": t.fields or [],
        "field_keys": template_keys(t), "source_type": t.source_type, "status": t.status,
        "expires_at": t.expires_at, "created_at": t.created_at,
    }


def visible_templates(db: Session, user: User):
    return db.scalars(
        select(Template).where(or_(Template.owner_id.is_(None), Template.owner_id == user.id)).order_by(Template.kind, Template.id)
    ).all()


def get_visible(db: Session, user: User, template_id: int) -> Template:
    t = db.get(Template, template_id)
    if not t or (t.owner_id is not None and t.owner_id != user.id):
        raise HTTPException(404, "양식을 찾을 수 없습니다.")
    return t


@router.get("/standard-fields")
def standard_fields():
    return [{"key": k, "label": m["label"], "group": m["group"], "synonyms": m["synonyms"]} for k, m in STANDARD_FIELDS.items()]


@router.get("")
def list_templates(kind: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = visible_templates(db, user)
    if kind:
        items = [t for t in items if t.kind == kind]
    return [to_out(t) for t in items]


@router.get("/search")
def search(q: str = "", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = [t for t in visible_templates(db, user) if t.status == "ready"]
    by_id = {t.id: t for t in items}
    results = ai.search_templates(q, items)
    return {
        "query": q,
        "ai_enabled": settings.ai_enabled,
        "results": [{"template": to_out(by_id[r["template_id"]]), "score": r["score"], "ai": r.get("ai", False)} for r in results if r["template_id"] in by_id],
    }


@router.get("/{template_id}")
def get_template(template_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return to_out(get_visible(db, user, template_id))


@router.post("/upload")
async def upload_template(file: UploadFile = File(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """기업 자체 양식 업로드 → 구조 분석 → 항목명을 표준 필드로 매핑 (사용자 확인 전 상태)."""
    ext = Path(file.filename or "").suffix.lower().lstrip(".")
    if ext not in ("docx", "pdf"):
        raise HTTPException(400, "Word(.docx) 또는 PDF 파일만 업로드할 수 있습니다. (.hwp는 Word/PDF로 변환 후 업로드)")
    data = await file.read()
    if len(data) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(400, f"파일은 {settings.MAX_UPLOAD_MB}MB 이하여야 합니다.")

    user_dir = settings.UPLOAD_DIR / str(user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    path = user_dir / f"{uuid.uuid4().hex}.{ext}"
    path.write_bytes(data)

    try:
        analysis = form_parser.analyze(path, ext)
    except Exception as e:
        path.unlink(missing_ok=True)
        raise HTTPException(400, f"양식을 분석하지 못했습니다: {e}")

    mapped, sent = ai.map_labels(analysis["items"])
    fields = [{**m, "context": it["context"], "location": it["location"]} for m, it in zip(mapped, analysis["items"])]
    name = Path(file.filename or "양식").stem
    t = Template(
        owner_id=user.id, kind="uploaded", name=name, category="자체 양식",
        description=f"업로드한 {ext.upper()} 양식 ({analysis.get('title') or name})",
        definition={"title": analysis.get("title") or name}, fields=fields,
        source_path=str(path), source_type=ext, status="analyzing",
        expires_at=datetime.utcnow() + timedelta(days=settings.UPLOAD_RETENTION_DAYS),
    )
    db.add(t)
    if sent["ai_used"]:
        db.add(AuditLog(user_id=user.id, action="ai_send", detail=f"양식 매핑: {sent['sent_chars']}자 전송, 마스킹 {sent['masked']}"))
    db.commit()
    return {
        "template": to_out(t),
        "analysis": {
            "title": analysis.get("title"),
            "detected": len(analysis["items"]),
            "mapped": sum(1 for f in fields if f["field_key"]),
            "ai_used": sent["ai_used"],
            "masked": sent["masked"],
            "sent_chars": sent["sent_chars"],
            "mode": "LLM" if sent["ai_used"] else "규칙 기반(동의어 사전)",
        },
    }


@router.put("/{template_id}/mapping")
def save_mapping(template_id: int, body: TemplateMappingIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = get_visible(db, user, template_id)
    if t.kind != "uploaded":
        raise HTTPException(400, "기본 양식은 수정할 수 없습니다.")
    for f in body.fields:
        if f.field_key and f.field_key not in STANDARD_FIELDS:
            raise HTTPException(400, f"알 수 없는 표준 필드: {f.field_key}")
    old = {(f.get("label"), str(f.get("location"))): f for f in t.fields}
    t.fields = [
        {**f.model_dump(), "method": "user" if old.get((f.label, str(f.location)), {}).get("field_key") != f.field_key else f.method}
        for f in body.fields
    ]
    if body.name:
        t.name = body.name
    if body.category:
        t.category = body.category
    t.status = "ready"
    db.commit()
    return to_out(t)


@router.delete("/{template_id}")
def delete_template(template_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """자체 양식 삭제 (원본 파일 즉시 삭제 — 3주차 보안 ⑤자동 삭제/사용자 요청 삭제)."""
    t = get_visible(db, user, template_id)
    if t.kind != "uploaded":
        raise HTTPException(400, "기본 양식은 삭제할 수 없습니다.")
    if db.scalar(select(Document.id).where(Document.template_id == t.id).limit(1)):
        raise HTTPException(409, "이 양식으로 작성된 서류가 있어 삭제할 수 없습니다. 서류를 먼저 삭제하세요.")
    if t.source_path:
        Path(t.source_path).unlink(missing_ok=True)
    db.add(AuditLog(user_id=user.id, action="file_delete", detail=f"자체 양식 '{t.name}' 삭제(사용자 요청)"))
    db.delete(t)
    db.commit()
    return {"ok": True}
