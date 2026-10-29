import uuid
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models import AuditLog, Contract, Document, Template, TemplateFavorite, User
from app.schemas import TemplateMappingIn, LibraryMetadataIn, LibraryPublishIn, TemplateRenameIn, FavoriteIn
from app.services.library import is_admin, require_admin, metadata, scope, recommendation
from app.services import ai, form_parser, renderer
from app.services.documents import template_keys, output_format
from app.services.pdf_forms import positioned, validate_locations
from app.standard_fields import STANDARD_FIELDS
from app.services.source_storage import persist, resolve, remove, track

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
    "staff_plan": "박담당 / 사업책임자 / 일정·품질·대외협의 총괄\n이개발 / 개발담당 / 서비스 구현 및 시험\n최디자인 / 디자인담당 / 화면설계 및 접근성 점검",
    "deliverables": "요구사항 정의서 1부 / 착수 후 2주 / 전자파일\n화면설계서 1부 / 설계 완료 시 / 전자파일\n소스코드·시험결과서·운영자 매뉴얼 각 1식 / 최종 납품 시",
    "quality_plan": "주간 진행현황과 쟁점사항을 발주처에 보고합니다.\n요구사항별 시험결과와 수정 이력을 관리하고 납품 전 확인합니다.\n자료 접근권한을 제한하고 과업 종료 시 계약조건에 따라 자료를 반납·파기합니다.",
    "activity_date": "2026. 10. 14.",
    "activity_time": "14:00 ~ 16:00",
    "activity_place": "샘플문화재단 회의실",
    "attendees": "김대표, 박담당, 이주무관",
    "activity_topic": "착수회의 및 요구사항 확정",
    "activity_details": "사업 목표와 일정, 주요 기능, 산출물 제출 방식을 협의했습니다.",
    "activity_result": "주간 진행상황을 공유하고 화면설계안을 제출하기로 했습니다.",
}


def sample_values(template):
    values = dict(SAMPLE_VALUES)
    if template.kind == 'custom':
        for section in template.definition['custom_plan']['layout']['sections']:
            if section['kind'] == 'table':
                values[section['key']] = ''
    return values


def to_out(t: Template) -> dict:
    return {
        "id": t.id, "kind": t.kind, "name": t.name, "category": t.category,
        "owner_id": t.owner_id,
        "description": t.description, "aliases": t.aliases or [], "fields": t.fields or [],
        "field_keys": template_keys(t), "source_type": t.source_type, "status": t.status,
        "expires_at": t.expires_at, "created_at": t.created_at,
        "library": {"scope": scope(t), **metadata(t)},
        "output_format": output_format(t),
        "custom_plan": t.definition.get("custom_plan") if t.kind == "custom" else None,
    }


def visible_templates(db: Session, user: User):
    rows = db.scalars(
        select(Template).where(or_(Template.owner_id.is_(None), Template.owner_id == user.id)).order_by(Template.kind, Template.id)
    ).all()
    if is_admin(user):
        rows = db.scalars(select(Template).order_by(Template.kind, Template.id)).all()
    return [t for t in rows if t.owner_id == user.id or (is_admin(user) and scope(t) == "organization") or
            (t.owner_id is None and t.status == "ready" and (t.kind == "builtin" or scope(t) == "organization"))]


def get_visible(db: Session, user: User, template_id: int) -> Template:
    t = db.get(Template, template_id)
    if not t or t not in visible_templates(db, user):
        raise HTTPException(404, "양식을 찾을 수 없습니다.")
    return t


def get_editable(db, user, template_id):
    t = get_visible(db, user, template_id)
    if t.kind == "builtin":
        raise HTTPException(400, "기본 양식은 수정할 수 없습니다.")
    if t.kind == "custom":
        raise HTTPException(400, "맞춤 양식은 새 초안 구성에서 수정하세요. 공개·업로드 매핑 변경은 지원하지 않습니다.")
    if scope(t) == "organization":
        require_admin(user)
        if db.scalar(select(Document.id).where(Document.template_id == t.id).limit(1)):
            raise HTTPException(409, "작성된 서류가 사용하는 지정 양식입니다. 새 버전으로 업로드하세요.")
    elif t.owner_id != user.id:
        raise HTTPException(403, "본인 양식만 수정할 수 있습니다.")
    return t


@router.get("/library-settings")
def library_settings(user: User = Depends(get_current_user)):
    return {"is_admin": is_admin(user), "user_id": user.id}


@router.get("/sources")
def library_sources(user: User = Depends(get_current_user)):
    from app.library_sources import SOURCES
    return SOURCES


@router.get("/standard-fields")
def standard_fields():
    return [{"key": k, "label": m["label"], "group": m["group"], "synonyms": m["synonyms"]} for k, m in STANDARD_FIELDS.items()]


@router.get("/favorites")
def favorites(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    visible = {t.id for t in visible_templates(db, user)}
    return [id_ for id_ in db.scalars(select(TemplateFavorite.template_id).where(TemplateFavorite.user_id == user.id)) if id_ in visible]


@router.get("/organizations")
def organizations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.services.library import normalize_issuer
    names = [metadata(t).get("organization", "") for t in visible_templates(db, user) if t.status == "ready"]
    names += list(db.scalars(select(Contract.client_name).where(Contract.user_id == user.id)))
    unique = {}
    for name in names:
        if name and name.strip():
            unique.setdefault(normalize_issuer(name), name.strip())
    return sorted(unique.values())


@router.get("")
def list_templates(kind: str | None = None, include_drafts: bool = False, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = [t for t in visible_templates(db, user) if t.status == "ready" or
             (include_drafts and (t.owner_id == user.id or is_admin(user)) and t.status != "archived")]
    if kind:
        items = [t for t in items if t.kind == kind]
    return [to_out(t) for t in items]


@router.get("/search")
def search(q: str = "", contract_id: int | None = None, project_code: str = "", client_name: str = "", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if contract_id:
        contract = db.get(Contract, contract_id)
        if not contract or contract.user_id != user.id:
            raise HTTPException(404, "계약을 찾을 수 없습니다.")
        client_name = contract.client_name
    items = [t for t in visible_templates(db, user) if t.status == "ready"]
    items = [t for t in items if recommendation(t, client_name, project_code) is not None]
    by_id = {t.id: t for t in items}
    results = ai.search_templates(q, items)
    results.sort(key=lambda r: (recommendation(by_id[r["template_id"]], client_name, project_code)[0], -r["score"]) if r["template_id"] in by_id else (99, 0))
    return {
        "query": q,
        "ai_enabled": settings.ai_enabled,
        "results": [{"template": to_out(by_id[r["template_id"]]), "score": r["score"], "ai": r.get("ai", False), "reason": recommendation(by_id[r["template_id"]], client_name, project_code)[1]} for r in results if r["template_id"] in by_id],
    }


@router.get("/{template_id}")
def get_template(template_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return to_out(get_visible(db, user, template_id))


@router.put("/{template_id}/favorite")
def set_favorite(template_id: int, body: FavoriteIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_visible(db, user, template_id)
    row = db.get(TemplateFavorite, (user.id, template_id))
    if body.favorite and row is None:
        db.add(TemplateFavorite(user_id=user.id, template_id=template_id))
    elif not body.favorite and row is not None:
        db.delete(row)
    db.commit()
    return {"favorite": body.favorite}


@router.put("/{template_id}/name")
def rename_template(template_id: int, body: TemplateRenameIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = get_visible(db, user, template_id)
    if t.kind == "builtin":
        raise HTTPException(400, "공통 양식의 이름은 변경할 수 없습니다.")
    if scope(t) == "organization":
        require_admin(user)
    elif t.owner_id != user.id:
        raise HTTPException(403, "본인 양식만 수정할 수 있습니다.")
    t.name = body.name
    db.add(AuditLog(user_id=user.id, action="template_rename", detail=f"양식 {t.id} 이름 변경: {body.name}"))
    db.commit()
    return to_out(t)


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
    t = get_visible(db, user, template_id)
    if t.kind != "builtin":
        raise HTTPException(400, "서비스 기본 양식만 샘플 미리보기를 지원합니다.")
    docx = renderer.render_builtin_docx(t.definition, SAMPLE_VALUES)
    pdf = renderer.docx_to_pdf_bytes(docx)
    return {
        "title": t.name,
        "output_format": t.definition.get("output_format", "hwpx"),
        "pages": renderer.pdf_preview_pages(pdf),
    }


@router.post("/upload")
async def upload_template(file: UploadFile = File(...), organization_library: bool = False, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """기업 자체 양식 업로드 → 구조 분석 → 항목명을 표준 필드로 매핑 (사용자 확인 전 상태)."""
    if organization_library:
        require_admin(user)
    ext = Path(file.filename or "").suffix.lower().lstrip(".")
    if ext not in ("docx", "pdf", "hwp", "hwpx"):
        raise HTTPException(400, "한글(.hwp, .hwpx), Word(.docx), PDF 파일을 업로드하세요.")
    if settings.CLOUD_MODE and ext == "hwp":
        raise HTTPException(400, "무료 웹 버전은 HWP 변환 서버가 없습니다. 한글에서 HWPX로 저장한 뒤 업로드하세요.")
    data = await file.read(settings.MAX_UPLOAD_MB * 1024 * 1024 + 1)
    if len(data) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(400, f"파일은 {settings.MAX_UPLOAD_MB}MB 이하여야 합니다.")

    user_dir = settings.UPLOAD_DIR / str(user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    path = user_dir / f"{uuid.uuid4().hex}.{ext}"
    path.write_bytes(data)
    if settings.CLOUD_MODE:
        track(path)

    try:
        analysis_path, analysis_type = path, ext
        if ext == 'hwp':
            if not data.startswith(bytes.fromhex('D0CF11E0A1B11AE1')):
                raise ValueError('HWP 파일 형식이 아닙니다. 한글에서 HWP 또는 HWPX로 저장한 파일을 올려주세요.')
            from app.services.hancom import convert
            analysis_path, analysis_type = path.with_suffix('.hwpx'), 'hwpx'
            await run_in_threadpool(convert, path, analysis_path, 'HWPX')
        analysis = form_parser.analyze(analysis_path, analysis_type)
    except HTTPException:
        path.unlink(missing_ok=True)
        if ext == 'hwp':
            path.with_suffix('.hwpx').unlink(missing_ok=True)
        raise
    except Exception:
        path.unlink(missing_ok=True)
        if ext == 'hwp':
            path.with_suffix('.hwpx').unlink(missing_ok=True)
        raise HTTPException(400, "양식을 분석하지 못했습니다. 손상·암호화 여부와 지원 파일 형식을 확인하세요.")

    mapped, sent = ai.map_labels(analysis["items"])
    fields = [{**m, "context": it["context"], "location": it["location"]} for m, it in zip(mapped, analysis["items"])]
    name = Path(file.filename or "양식").stem
    t = Template(
        owner_id=user.id, kind="uploaded", name=name, category="자체 양식",
        description=f"업로드한 {ext.upper()} 양식 ({analysis.get('title') or name})",
        definition={"title": analysis.get("title") or name, "library": {"scope": "organization" if organization_library else "private"}}, fields=fields,
        source_path=persist(db, path, user.id), source_type=ext, status="analyzing",
        expires_at=None if organization_library else datetime.utcnow() + timedelta(days=settings.UPLOAD_RETENTION_DAYS),
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
    t = get_editable(db, user, template_id)
    for f in body.fields:
        if f.field_key and f.field_key not in STANDARD_FIELDS:
            raise HTTPException(400, f"알 수 없는 표준 필드: {f.field_key}")
    candidate = Template(source_path=t.source_path, source_type=t.source_type, fields=[f.model_dump() for f in body.fields])
    if positioned(candidate):
        validate_locations(candidate)
    old = {(f.get("label"), str(f.get("location"))): f for f in t.fields}
    t.fields = [
        {**f.model_dump(), "method": "user" if old.get((f.label, str(f.location)), {}).get("field_key") != f.field_key else f.method}
        for f in body.fields
    ]
    if body.name:
        t.name = body.name
    if body.category:
        t.category = body.category
    t.status = "review_pending" if scope(t) == "organization" else "ready"
    if scope(t) == "organization":
        t.owner_id = user.id
    db.commit()
    return to_out(t)


@router.put("/{template_id}/metadata")
def save_metadata(template_id: int, body: LibraryMetadataIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = get_editable(db, user, template_id)
    if body.scope == "organization" or scope(t) == "organization":
        require_admin(user)
    info = body.model_dump(mode="json")
    if body.document_type:
        t.aliases = list(dict.fromkeys([*(t.aliases or []), body.document_type]))
    t.definition = {**t.definition, "library": info}
    t.owner_id = user.id
    t.status = "review_pending" if body.scope == "organization" else "analyzing"
    t.expires_at = None if body.scope == "organization" else datetime.utcnow() + timedelta(days=settings.UPLOAD_RETENTION_DAYS)
    db.commit()
    return to_out(t)


@router.post("/{template_id}/publish")
def publish(template_id: int, body: LibraryPublishIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_admin(user)
    t = get_editable(db, user, template_id)
    info = metadata(t)
    if scope(t) != "organization" or not all(info.get(k) for k in ("organization", "document_type", "source_url", "version", "usage_terms")):
        raise HTTPException(400, "발주처·서류 종류·출처·버전·이용 조건을 입력하세요.")
    if not all((body.mapping_checked, body.output_checked, body.rights_checked)) or not info.get("review_note"):
        raise HTTPException(400, "매핑·출력·이용 조건을 확인하고 검토 메모를 남겨 주세요.")
    source = resolve(t)
    if not source or not source.is_file() or (t.source_type not in ('docx', 'hwp', 'hwpx') and not positioned(t)):
        raise HTTPException(400, "지정 양식은 DOCX·HWP·HWPX 또는 입력 위치를 검토한 PDF가 필요합니다.")
    if positioned(t):
        validate_locations(t)
    if not template_keys(t) or any(not f.get("field_key") for f in t.fields):
        raise HTTPException(400, "입력 칸을 모두 매핑한 뒤 공개하세요.")
    t.definition = {**t.definition, "library": {**info, "reviewed_at": datetime.utcnow().isoformat(), "reviewer_id": user.id}}
    t.owner_id, t.status, t.expires_at = None, "ready", None
    db.add(AuditLog(user_id=user.id, action="template_publish", detail=f"지정 양식 공개: {t.name} / {info['version']}"))
    db.commit()
    return to_out(t)


@router.get("/{template_id}/review-preview")
def review_preview(template_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = get_visible(db, user, template_id)
    from app.services.documents import preview_html
    doc = Document(template=t, values=sample_values(t))
    return {"html": preview_html(doc)}


@router.get("/{template_id}/original")
def original(template_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from fastapi.responses import FileResponse
    t = get_visible(db, user, template_id)
    source = resolve(t)
    if not source or not source.is_file():
        raise HTTPException(404, "보관된 원본이 없습니다.")
    return FileResponse(source, filename=f"{t.name}.{t.source_type}")


@router.get("/{template_id}/sample-file")
def sample_file(template_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.services.documents import build_native
    t = get_visible(db, user, template_id)
    doc = Document(template=t, values=sample_values(t))
    data, extension, media = build_native(doc)
    return Response(data, media_type=media, headers={"Content-Disposition": f'attachment; filename="sample.{extension}"'})


@router.get('/{template_id}/review-preview-pages')
def review_preview_pages(template_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.services.documents import build_pdf
    template = get_visible(db, user, template_id)
    return {'pages': renderer.pdf_preview_pages(build_pdf(Document(template=template, values=sample_values(template))))}


@router.delete("/{template_id}")
def delete_template(template_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """자체 양식 삭제 (원본 파일 즉시 삭제 — 3주차 보안 ⑤자동 삭제/사용자 요청 삭제)."""
    t = get_visible(db, user, template_id)
    if t.kind != "custom":
        t = get_editable(db, user, template_id)
    elif t.owner_id != user.id:
        raise HTTPException(404, "양식을 찾을 수 없습니다.")
    if t.kind not in ("uploaded", "custom"):
        raise HTTPException(400, "기본 양식은 삭제할 수 없습니다.")
    if db.scalar(select(Document.id).where(Document.template_id == t.id).limit(1)):
        raise HTTPException(409, "이 양식으로 작성된 서류가 있어 삭제할 수 없습니다. 서류를 먼저 삭제하세요.")
    remove(db, t)
    from sqlalchemy import delete
    db.execute(delete(TemplateFavorite).where(TemplateFavorite.template_id == t.id))
    db.add(AuditLog(user_id=user.id, action="file_delete", detail=f"자체 양식 '{t.name}' 삭제(사용자 요청)"))
    db.delete(t)
    db.commit()
    return {"ok": True}
