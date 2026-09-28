from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import Company, User
from app.schemas import CompanyIn, CompanyOut

router = APIRouter(prefix="/company", tags=["company"])


def get_or_create_company(db: Session, user: User) -> Company:
    company = user.company
    if company is None:
        company = Company(user_id=user.id)
        db.add(company)
        db.commit()
    return company


@router.get("", response_model=CompanyOut)
def get_company(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_or_create_company(db, user)


@router.put("", response_model=CompanyOut)
def update_company(body: CompanyIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    company = get_or_create_company(db, user)
    for k, v in body.model_dump().items():
        setattr(company, k, v.strip())
    db.commit()
    return company
