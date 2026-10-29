"""User-controlled deletion. Provider backups and exported copies are separate."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_sensitive
from app.models import AuditLog, Company, Contract, Template, TemplateFavorite, User
from app.services.library import scope
from app.services.source_storage import remove

router = APIRouter(prefix="/privacy", tags=["privacy"])


@router.delete("/data")
def delete_data(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_sensitive(request, db, user, "data:delete")
    for contract in db.scalars(select(Contract).where(Contract.user_id == user.id)).all():
        db.delete(contract)
    db.flush()
    db.execute(delete(TemplateFavorite).where(TemplateFavorite.user_id == user.id))
    for template in db.scalars(select(Template).where(Template.owner_id == user.id)).all():
        if scope(template) == "private":
            remove(db, template)
            db.execute(delete(TemplateFavorite).where(TemplateFavorite.template_id == template.id))
            db.delete(template)
    if user.company:
        db.delete(user.company)
    db.execute(update(AuditLog).where(AuditLog.user_id == user.id).values(detail="사용자 요청으로 상세정보 삭제"))
    db.add(AuditLog(user_id=user.id, action="data_delete", detail="계약·서류·개인 양식·회사정보·인감 삭제. 계정 및 최소 보안 이력은 유지."))
    db.commit()
    return {"ok": True, "note": "제공업체 백업과 이미 다운로드·발송한 파일은 별도 보관 정책을 따릅니다."}
