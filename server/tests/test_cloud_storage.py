import tempfile
import unittest
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.core.database import Base
from app.core.config import settings
from app.models import StoredFile, Template, User
from app.services.source_storage import persist, resolve, remove, request_files


class CloudStorageTests(unittest.TestCase):
    def test_source_survives_local_file_removal_and_deleted_source_is_not_cached(self):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        with Session(engine) as db, tempfile.TemporaryDirectory() as tmp, patch.object(settings, "CLOUD_MODE", True), patch.object(settings, "UPLOAD_DIR", Path(tmp)):
            user = User(email="cloud@example.test", password_hash="unused")
            db.add(user); db.flush()
            path = Path(tmp) / (uuid.uuid4().hex + ".docx")
            path.write_bytes(b"original source")
            ref = persist(db, path, user.id)
            t = Template(owner_id=user.id, kind="uploaded", name="test", source_path=ref, source_type="docx")
            db.add(t); db.commit()
            path.unlink()
            token = request_files.set([])
            try:
                materialized = resolve(t)
                self.assertEqual(materialized.read_bytes(), b"original source")
                materialized.unlink()
                remove(db, t); db.commit()
                self.assertEqual(db.query(StoredFile).count(), 0)
                with self.assertRaises(HTTPException) as exc:
                    resolve(t)
                self.assertEqual(exc.exception.status_code, 410)
            finally:
                request_files.reset(token)
        engine.dispose()

    def test_expired_source_is_blocked_even_before_purge(self):
        t = Template(source_path="dbfile://" + "a" * 32 + ".hwpx", expires_at=datetime.utcnow() - timedelta(days=1))
        with self.assertRaises(HTTPException) as exc:
            resolve(t)
        self.assertEqual(exc.exception.status_code, 410)
