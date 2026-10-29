from fastapi import APIRouter, Depends, File, UploadFile, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_sensitive
from app.models import AuditLog, Company, User
from app.schemas import CompanyIn, CompanyOut, SealSizeIn
from app.services.seal import MAX_BYTES, normalize_seal

router = APIRouter(prefix="/company", tags=["company"])


def company_out(company):
    result = CompanyOut.model_validate(company)
    result.has_seal = bool(company.seal_image)
    result.seal_image = ""
    return result


def get_or_create_company(db: Session, user: User) -> Company:
    company = user.company
    if company is None:
        company = Company(user_id=user.id)
        db.add(company)
        db.commit()
    return company


@router.get("", response_model=CompanyOut)
def get_company(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return company_out(get_or_create_company(db, user))


@router.put("", response_model=CompanyOut)
def update_company(body: CompanyIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    company = get_or_create_company(db, user)
    for k, v in body.model_dump().items():
        setattr(company, k, v.strip())
    db.commit()
    return company_out(company)


@router.post('/seal', response_model=CompanyOut)
async def upload_seal(request: Request, file: UploadFile = File(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_sensitive(request, db, user, "seal:manage")
    data = await file.read(MAX_BYTES + 1)
    image = normalize_seal(data)
    company = get_or_create_company(db, user)
    company.seal_image = image
    db.add(AuditLog(user_id=user.id, action="seal_upload", detail="인감 등록·교체"))
    db.commit()
    return company_out(company)


@router.put('/seal', response_model=CompanyOut)
def resize_seal(body: SealSizeIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_sensitive(request, db, user, "seal:manage")
    company = get_or_create_company(db, user)
    company.seal_size_mm = body.size_mm
    db.commit()
    return company_out(company)


@router.delete('/seal', response_model=CompanyOut)
def remove_seal(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_sensitive(request, db, user, "seal:manage")
    company = get_or_create_company(db, user)
    company.seal_image = ''
    db.add(AuditLog(user_id=user.id, action="seal_delete", detail="인감 삭제"))
    db.commit()
    return company_out(company)


@router.get('/seal')
def view_seal(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_sensitive(request, db, user, "seal:read")
    company = get_or_create_company(db, user)
    return {"seal_image": company.seal_image}
