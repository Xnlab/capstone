import io
import zipfile
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import AuditLog, Contract, Document, User
from app.routers.company import get_or_create_company
from app.routers.templates import get_visible
from app.schemas import ContractIn, DocumentCreate, MailIn
from app.services import ai, renderer
from app.services.documents import auto_values, build_docx, safe_filename, to_out
from app.services.mailer import send_mail
from app.services.validator import validate
from app.standard_fields import base_values

router = APIRouter(prefix="/contracts", tags=["contracts"])


def get_owned(db: Session, user: User, contract_id: int) -> Contract:
    """접근 통제: 본인 계약만 조회 가능 (3주차 보안 ④)."""
    c = db.get(Contract, contract_id)
    if not c or c.user_id != user.id:
        raise HTTPException(404, "계약을 찾을 수 없습니다.")
    return c


def contract_out(c: Contract, count: int | None = None) -> dict:
    return {
        "id": c.id, "contract_title": c.contract_title, "client_name": c.client_name, "amount": c.amount,
        "start_date": c.start_date, "end_date": c.end_date, "description": c.description,
        "created_at": c.created_at, "document_count": len(c.documents) if count is None else count,
    }


@router.get("")
def list_contracts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Contract, func.count(Document.id))
        .outerjoin(Document, Document.contract_id == Contract.id)
        .where(Contract.user_id == user.id)
        .group_by(Contract.id)
        .order_by(Contract.created_at.desc())
    ).all()
    return [contract_out(c, n) for c, n in rows]


@router.post("")
def create_contract(body: ContractIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.start_date and body.end_date and body.start_date > body.end_date:
        raise HTTPException(400, "착수일이 완료일보다 늦을 수 없습니다.")
    c = Contract(user_id=user.id, **body.model_dump())
    db.add(c)
    db.commit()
    return contract_out(c, 0)


@router.get("/{contract_id}")
def get_contract(contract_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return contract_out(get_owned(db, user, contract_id))


@router.put("/{contract_id}")
def update_contract(contract_id: int, body: ContractIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = get_owned(db, user, contract_id)
    if body.start_date and body.end_date and body.start_date > body.end_date:
        raise HTTPException(400, "착수일이 완료일보다 늦을 수 없습니다.")
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    db.commit()
    return contract_out(c)


@router.delete("/{contract_id}")
def delete_contract(contract_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.delete(get_owned(db, user, contract_id))
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- 서류
@router.get("/{contract_id}/documents")
def list_documents(contract_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = get_owned(db, user, contract_id)
    return [to_out(d) for d in sorted(c.documents, key=lambda d: d.id)]


@router.post("/{contract_id}/documents")
def create_document(contract_id: int, body: DocumentCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """양식 선택 → 회사·계약정보 자동 적용 → 서류 생성 (CASE 1·2 공통)."""
    c = get_owned(db, user, contract_id)
    t = get_visible(db, user, body.template_id)
    if t.status != "ready":
        raise HTTPException(400, "양식 항목 매핑을 먼저 확인·저장해 주세요.")
    company = get_or_create_company(db, user)
    doc = Document(contract_id=c.id, template_id=t.id, title=t.name, values=auto_values(db, user.id, t, company, c))
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return to_out(doc)


@router.post("/{contract_id}/validate")
def validate_contract(contract_id: int, with_ai: bool = False, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """AI 검토(누락·오류·서류 간 불일치). 규칙 검증 + (선택) LLM 문장 검토."""
    c = get_owned(db, user, contract_id)
    docs = sorted(c.documents, key=lambda d: d.id)
    master = base_values(get_or_create_company(db, user), c)
    result = validate(docs, master)
    result["ai_comments"] = []
    if with_ai:
        for d in docs:
            comments = ai.review_text(d.title, renderer.docx_to_text(build_docx(d)))
            if comments:
                result["ai_comments"].append({"document_id": d.id, "title": d.title, "comments": comments})
        db.add(AuditLog(user_id=user.id, action="ai_send", detail=f"문장 검토 {len(docs)}건 (계약 {c.id}, 마스킹 후 전송)"))
    for d in docs:
        has_error = any(d.id in i["document_ids"] and i["severity"] == "error" for i in result["issues"])
        d.status = "draft" if has_error else "reviewed"
    db.commit()
    return result


def _render_files(docs: list[Document], fmt: str) -> list[tuple[str, bytes, str]]:
    files = []
    for i, d in enumerate(docs, 1):
        docx = build_docx(d)
        name = f"{i:02d}_{safe_filename(d.title)}"
        if fmt in ("docx", "both"):
            files.append((f"{name}.docx", renderer.docx_bytes(docx), "vnd.openxmlformats-officedocument.wordprocessingml.document"))
        if fmt in ("pdf", "both"):
            files.append((f"{name}.pdf", renderer.docx_to_pdf_bytes(docx), "pdf"))
    return files


@router.get("/{contract_id}/export")
def export_zip(contract_id: int, format: str = "both", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = get_owned(db, user, contract_id)
    docs = sorted(c.documents, key=lambda d: d.id)
    if not docs:
        raise HTTPException(400, "작성된 서류가 없습니다.")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data, _ in _render_files(docs, format):
            z.writestr(name, data)
    buf.seek(0)
    fname = quote(f"{safe_filename(c.contract_title)}_제출서류.zip")
    return StreamingResponse(buf, media_type="application/zip", headers={"Content-Disposition": f"attachment; filename*=UTF-8''{fname}"})


@router.post("/{contract_id}/mail")
def mail_documents(contract_id: int, body: MailIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = get_owned(db, user, contract_id)
    docs = [d for d in sorted(c.documents, key=lambda d: d.id) if d.id in set(body.document_ids)]
    if not docs:
        raise HTTPException(400, "보낼 서류를 선택하세요.")
    company = get_or_create_company(db, user)
    subject = body.subject or f"[{company.company_name or '제출'}] {c.contract_title} 관련 서류 제출"
    text = body.body or f"안녕하세요. {c.contract_title} 관련 서류를 첨부하여 제출합니다.\n\n첨부: " + ", ".join(d.title for d in docs)
    result = send_mail(body.to, subject, text, _render_files(docs, body.format))
    db.add(AuditLog(user_id=user.id, action="mail_send", detail=f"계약 {c.id} 서류 {len(docs)}건 → {body.to} (mock={result['mock']})"))
    db.commit()
    return {**result, "to": body.to, "count": len(docs)}
