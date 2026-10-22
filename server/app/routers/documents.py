from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import AuditLog, Document, User
from app.routers.company import get_or_create_company
from app.schemas import DocumentUpdate
from app.services import ai, renderer
from app.services.documents import auto_values, build_docx, build_native, build_pdf, safe_filename, template_keys, to_out
from app.standard_fields import base_values, korean_amount

router = APIRouter(prefix="/documents", tags=["documents"])


def get_owned_doc(db: Session, user: User, document_id: int) -> Document:
    d = db.get(Document, document_id)
    if not d or d.contract.user_id != user.id:
        raise HTTPException(404, "서류를 찾을 수 없습니다.")
    return d


@router.get("/{document_id}")
def get_document(document_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return to_out(get_owned_doc(db, user, document_id))


@router.put("/{document_id}")
def update_document(document_id: int, body: DocumentUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """사용자 수정. 수정 후에는 다시 검증이 필요하므로 상태를 draft로 되돌린다."""
    d = get_owned_doc(db, user, document_id)
    allowed = set(template_keys(d.template))
    changed = {k: v for k, v in body.values.items() if k in allowed}
    if "payment_amount" in changed and "payment_amount_korean" in allowed:
        amount = int("".join(ch for ch in changed["payment_amount"] if ch.isdigit()) or 0)
        changed["payment_amount_korean"] = korean_amount(amount) if amount else ""
    d.values = {**d.values, **changed}
    d.status = "draft"
    db.commit()
    return to_out(d)


@router.delete("/{document_id}")
def delete_document(document_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.delete(get_owned_doc(db, user, document_id))
    db.commit()
    return {"ok": True}


@router.post("/{document_id}/reapply")
def reapply(document_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """회사·계약정보를 다시 적용 (수정한 값은 덮어씀)."""
    d = get_owned_doc(db, user, document_id)
    d.values = auto_values(db, user.id, d.template, get_or_create_company(db, user), d.contract)
    d.status = "draft"
    db.commit()
    return to_out(d)


@router.post("/{document_id}/generate/{field_key}")
def generate_field(document_id: int, field_key: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = get_owned_doc(db, user, document_id)
    if field_key != "work_summary":
        raise HTTPException(400, "AI 생성은 문장형 항목(과업 개요)만 지원합니다.")
    base = base_values(get_or_create_company(db, user), d.contract)
    text, used = ai.generate_work_summary(base)
    if used:
        db.add(AuditLog(user_id=user.id, action="ai_generate", detail=f"과업 개요 재생성 (서류 {d.id})"))
        db.commit()
    return {"field_key": field_key, "value": text, "ai_used": used}


@router.get("/{document_id}/preview")
def preview(document_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = get_owned_doc(db, user, document_id)
    return {"html": renderer.docx_to_html(build_docx(d))}


@router.get("/{document_id}/preview-pages")
def preview_pages(document_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = get_owned_doc(db, user, document_id)
    pdf = build_pdf(d)
    return {"pages": renderer.pdf_preview_pages(pdf)}


@router.get("/{document_id}/download")
def download(document_id: int, format: str = "native", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = get_owned_doc(db, user, document_id)
    name = safe_filename(f"{d.contract.contract_title}_{d.title}")
    if format == "pdf":
        data, media, ext = build_pdf(d), "application/pdf", "pdf"
    elif format == "native":
        data, ext, media = build_native(d)
    elif format == "docx":
        docx = build_docx(d)
        data, media, ext = renderer.docx_bytes(docx), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"
    else:
        raise HTTPException(400, "format은 native, pdf 또는 docx")
    return Response(data, media_type=media, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name + '.' + ext)}"})

