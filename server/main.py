"""AI 기반 계약·행정서류 자동화 웹 서비스 — API 서버.

실행: uvicorn main:app --reload --port 8000
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.builtin_templates import BUILTIN_TEMPLATES
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine, get_db
from app.core.security import get_current_user
from app.models import AuditLog, Template, User
from app.routers import auth, company, contracts, documents, templates

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("app")


def ensure_company_columns():
    """Add optional reusable business/bank fields to an existing database."""
    existing = {column["name"] for column in inspect(engine).get_columns("companies")}
    columns = {
        "business_type": "VARCHAR(100)",
        "business_item": "VARCHAR(100)",
        "bank_name": "VARCHAR(50)",
        "account_number": "VARCHAR(50)",
        "account_holder": "VARCHAR(100)",
    }
    with engine.begin() as connection:
        for name, sql_type in columns.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE companies ADD COLUMN {name} {sql_type} NOT NULL DEFAULT ''"))


def seed_builtin_templates(db: Session):
    """기본 양식 라이브러리를 DB에 반영 (코드 정의가 정본)."""
    active_keys = {t["key"] for t in BUILTIN_TEMPLATES}
    for t in BUILTIN_TEMPLATES:
        row = db.scalar(select(Template).where(Template.key == t["key"]))
        definition = dict(t["definition"])
        if row is None:
            row = Template(key=t["key"], kind="builtin", owner_id=None)
            db.add(row)
        row.name, row.category, row.description = t["name"], t["category"], t["description"]
        row.aliases, row.definition, row.status = t["aliases"], definition, "ready"
    for row in db.scalars(select(Template).where(Template.kind == "builtin")).all():
        if row.key not in active_keys:
            row.status = "archived"
    db.commit()


def purge_expired_uploads(db: Session) -> int:
    """보관기간이 지난 업로드 원본 파일 삭제 (양식의 매핑 정보는 남겨 재구성 가능)."""
    rows = db.scalars(select(Template).where(Template.kind == "uploaded", Template.expires_at < datetime.utcnow(), Template.source_path.is_not(None))).all()
    for t in rows:
        Path(t.source_path).unlink(missing_ok=True)
        db.add(AuditLog(user_id=t.owner_id, action="file_purge", detail=f"보관기간 경과로 '{t.name}' 원본 삭제"))
        t.source_path = None
    db.commit()
    return len(rows)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    ensure_company_columns()
    with SessionLocal() as db:
        seed_builtin_templates(db)
        n = purge_expired_uploads(db)
    log.info("AI 모드: %s / 만료 원본 삭제 %d건", "LLM" if settings.ai_enabled else "규칙 기반", n)
    yield


app = FastAPI(title="계약·행정서류 자동화 API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"], expose_headers=["Content-Disposition"])

API = "/api/v1"
for r in (auth.router, company.router, contracts.router, documents.router, templates.router):
    app.include_router(r, prefix=API)


@app.get(f"{API}/health")
def health():
    return {"status": "ok", "ai_mode": "llm" if settings.ai_enabled else "rule", "mail_mode": "smtp" if settings.SMTP_HOST else "mock"}


@app.get(f"{API}/audit-logs")
def audit_logs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """내 민감정보 처리 이력 (AI 전송·메일·파일 삭제)."""
    rows = db.scalars(select(AuditLog).where(AuditLog.user_id == user.id).order_by(AuditLog.id.desc()).limit(100)).all()
    return [{"id": r.id, "action": r.action, "detail": r.detail, "created_at": r.created_at} for r in rows]
