"""Library metadata and deterministic issuer matching. No external calls."""
import re

from fastapi import HTTPException
from app.core.config import settings


def is_admin(user):
    return user.email.lower() in settings.LIBRARY_ADMIN_EMAILS


def require_admin(user):
    if not is_admin(user):
        raise HTTPException(403, "라이브러리 관리자만 공개 양식을 관리할 수 있습니다.")


def metadata(template):
    return (template.definition or {}).get("library", {})


def scope(template):
    return metadata(template).get("scope", "common" if template.kind == "builtin" else "private")


def normalize_issuer(value):
    value = re.sub(r"주식회사|\(주\)|㈜", "", value or "")
    return re.sub(r"\s+", "", value).casefold()


def recommendation(template, client_name, project_code=""):
    info = metadata(template)
    if scope(template) == "organization":
        if not client_name or normalize_issuer(info.get("organization")) != normalize_issuer(client_name):
            return None
        code = info.get("project_code", "")
        if code and code != project_code:
            return None
        return (0, "해당 사업 지정 양식") if code else (1, "발주처 양식 · 적용 버전을 확인하세요")
    if scope(template) == "common":
        return 2, "공통 양식으로 초안 작성"
    return 3, "내 업로드 양식"
