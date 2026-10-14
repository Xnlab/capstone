import uuid
import base64
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models import AuditLog, Document, Template, User
from app.schemas import TemplateMappingIn
from app.services import ai, form_parser, renderer
from app.services.documents import template_keys
from app.standard_fields import STANDARD_FIELDS

router = APIRouter(prefix="/templates", tags=["templates"])


SAMPLE_VALUES = {
    "company_name": "주식회사 샘플",
    "representative": "김대표",
    "business_number": "123-45-67890",
    "address": "서울특별시 중구 세종대로 1",
    "phone": "02-1234-5678",
    "email": "hello@example.com",
    "manager_name": "박담당",
    "business_type": "정보통신업",
    "business_item": "소프트웨어 개발",
    "bank_name": "샘플은행",
    "account_number": "123-456-789012",
    "account_holder": "주식회사 샘플",
    "contract_title": "지역문화 행사 안내 웹서비스 구축 용역",
    "client_name": "샘플문화재단",
    "amount": "11,000,000원",
    "amount_korean": "일금 일천백만원정",
    "supply_amount": "10,000,000원",
    "vat": "1,000,000원",
    "start_date": "2026. 10. 15.",
    "end_date": "2026. 12. 20.",
    "period": "2026. 10. 15. ~ 2026. 12. 20.",
    "description": "반응형 웹서비스 기획, 디자인, 개발 및 운영자 교육",
    "submit_date": "2026. 10. 14.",
    "contract_date": "2026. 10. 14.",
    "contract_number": "2026-용역-1014",
    "document_number": "샘플-2026-014",
    "advance_amount": "5,500,000원",
    "payment_amount": "11,000,000원",
    "payment_amount_korean": "일금 일천백만원정",
    "usage_purpose": "개발 인건비 및 클라우드 이용료",
    "quote_items": "서비스 기획·디자인|1|3000000|\n웹서비스 개발|1|5000000|\n시험·운영자 교육|1|2000000|",
    "detail_items": "기획 및 화면설계|1|2500000|\nUI 디자인|1|2500000|\n프론트·백엔드 개발|1|5000000|",
    "completion_details": "계약 범위의 웹서비스 구축, 기능시험 및 운영자 교육을 완료했습니다.",
    "work_summary": "지역문화 행사 정보를 쉽게 확인하고 운영자가 직접 관리할 수 있는 웹서비스를 구축합니다.",
    "work_method": "1. 요구사항을 확정합니다.\n2. 설계와 개발을 단계별로 수행합니다.\n3. 검수 의견을 반영합니다.",
    "work_schedule": "요구사항 분석 → 화면설계 → 개발 → 통합시험 → 검수",
    "activity_date": "2026. 10. 14.",
    "activity_time": "14:00 ~ 16:00",
    "activity_place": "샘플문화재단 회의실",
    "attendees": "김대표, 박담당, 이주무관",
    "activity_topic": "착수회의 및 요구사항 확정",
    "activity_details": "사업 목표와 일정, 주요 기능, 산출물 제출 방식을 협의했습니다.",
    "activity_result": "주간 진행상황을 공유하고 화면설계안을 제출하기로 했습니다.",
}


def to_out(t: Template) -> dict:
    return {
        "id": t.id, "kind": t.kind, "name": t.name, "category": t.category,
        "description": t.description, "aliases": t.aliases or [], "fields": t.fields or [],
        "field_keys": template_keys(t), "source_type": t.source_type, "status": t.status,
        "expires_at": t.expires_at, "created_at": t.created_at,
        "output_format": t.definition.get("output_format", "docx") if t.kind == "builtin" else "docx",
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
    items = [t for t in visible_templates(db, user) if t.status == "ready"]
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


@router.get("/{template_id}/preview")
def preview_template(template_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Render a browser preview with clearly fictional sample values."""
    t = get_visible(db, user, template_id)
    if t.kind != "builtin":
        raise HTTPException(400, "서비스 기본 양식만 샘플 미리보기를 지원합니다.")
    docx = renderer.render_builtin_docx(t.definition, SAMPLE_VALUES)
    return {
        "title": t.name,
        "html": renderer.docx_to_html(docx),
        "output_format": t.definition.get("output_format", "hwpx"),
    }


@router.get("/{template_id}/preview-file")
def preview_template_file(template_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return a real A4 PDF preview so page layout and page breaks are visible."""
    t = get_visible(db, user, template_id)
    if t.kind != "builtin":
        raise HTTPException(400, "서비스 기본 양식만 샘플 미리보기를 지원합니다.")
    docx = renderer.render_builtin_docx(t.definition, SAMPLE_VALUES)
    data = renderer.docx_to_pdf_bytes(docx)
    return Response(
        data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="template-{t.id}-preview.pdf"'},
    )


@router.get("/{template_id}/preview-pages")
def preview_template_pages(template_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Render every A4 preview page to PNG for browsers without an embedded PDF viewer."""
    import pymupdf

    t = get_visible(db, user, template_id)
    if t.kind != "builtin":
        raise HTTPException(400, "서비스 기본 양식만 샘플 미리보기를 지원합니다.")
    docx = renderer.render_builtin_docx(t.definition, SAMPLE_VALUES)
    pdf = renderer.docx_to_pdf_bytes(docx)
    pages = []
    with pymupdf.open(stream=pdf, filetype="pdf") as document:
        for page in document:
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(1.6, 1.6), alpha=False)
            encoded = base64.b64encode(pixmap.tobytes("png")).decode("ascii")
            pages.append({"data": f"data:image/png;base64,{encoded}", "width": pixmap.width, "height": pixmap.height})
    return {
        "title": t.name,
        "output_format": t.definition.get("output_format", "hwpx"),
        "pages": pages,
    }


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
