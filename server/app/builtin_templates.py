"""서비스 기본 양식 라이브러리 (2주차 설계).

각 양식은 렌더링 정의(제목·표·본문·첨부·서명란)로 표현하고, 값은 표준 필드 키로만 참조한다.
본문 안의 {field_key} 는 작성 시 값으로 치환된다.
"""

import re

SIGN_BLOCK = True

BUILTIN_TEMPLATES: list[dict] = [
    {
        "key": "commencement",
        "name": "착수계",
        "category": "착수·완료",
        "description": "계약 체결 후 용역(공사)을 착수했음을 발주처에 신고하는 서류",
        "aliases": ["착수신고서", "착수 신고서", "착수보고", "착공계"],
        "definition": {
            "title": "착  수  계",
            "table": [
                ["계 약 명", "contract_title"],
                ["계약금액", "amount"],
                ["계약기간", "period"],
                ["착 수 일", "start_date"],
                ["완료예정일", "end_date"],
                ["과업 개요", "work_summary"],
            ],
            "body": "위 계약에 따라 {start_date}부로 착수하였기에 관련 서류를 첨부하여 착수계를 제출합니다.",
            "attachments": ["과업수행계획서 1부", "보안서약서 1부", "사용인감계 1부"],
            "signature": SIGN_BLOCK,
            "recipient": "{client_name} 귀하",
        },
        "required": ["contract_title", "amount", "period", "start_date", "company_name", "representative", "client_name"],
    },
    {
        "key": "completion",
        "name": "완료계",
        "category": "착수·완료",
        "description": "용역(공사)을 완료했음을 발주처에 신고하는 서류",
        "aliases": ["준공계", "완료신고서", "용역완료계", "준공신고서"],
        "definition": {
            "title": "완  료  계",
            "table": [
                ["계 약 명", "contract_title"],
                ["계약금액", "amount"],
                ["계약기간", "period"],
                ["완 료 일", "end_date"],
            ],
            "body": "위 계약에 대하여 {end_date}부로 과업을 완료하였기에 완료계를 제출합니다.",
            "attachments": ["완료보고서 1부"],
            "signature": SIGN_BLOCK,
            "recipient": "{client_name} 귀하",
        },
        "required": ["contract_title", "amount", "period", "end_date", "company_name", "representative"],
    },
    {
        "key": "quotation",
        "name": "견적서",
        "category": "계약·금액",
        "description": "계약금액을 공급가액·부가세로 나눠 제시하는 견적서",
        "aliases": ["견적", "견적서류", "가격견적서"],
        "definition": {
            "title": "견  적  서",
            "table": [
                ["수    신", "client_name"],
                ["건    명", "contract_title"],
                ["견적금액", "amount_korean"],
                ["공급가액", "supply_amount"],
                ["부 가 세", "vat"],
                ["합    계", "amount"],
                ["사업자등록번호", "business_number"],
                ["상    호", "company_name"],
                ["주    소", "address"],
                ["연 락 처", "phone"],
            ],
            "body": "아래와 같이 견적합니다. (부가가치세 포함)",
            "signature": SIGN_BLOCK,
        },
        "required": ["client_name", "contract_title", "amount", "amount_korean", "company_name", "business_number"],
    },
    {
        "key": "cost_breakdown",
        "name": "산출내역서",
        "category": "계약·금액",
        "description": "계약금액의 산출 근거(공급가액·부가세)를 정리한 서류",
        "aliases": ["산출 내역서", "내역서", "원가계산서", "비용산출서"],
        "definition": {
            "title": "산 출 내 역 서",
            "table": [
                ["계 약 명", "contract_title"],
                ["공급가액", "supply_amount"],
                ["부가가치세(10%)", "vat"],
                ["총 계약금액", "amount"],
                ["금액(한글)", "amount_korean"],
            ],
            "body": "상기 금액은 과업 수행에 필요한 인건비·경비 등을 포함한 금액입니다.",
            "signature": SIGN_BLOCK,
        },
        "required": ["contract_title", "supply_amount", "vat", "amount"],
    },
    {
        "key": "security_pledge",
        "name": "보안서약서",
        "category": "보안·서약",
        "description": "과업 수행 중 취득한 정보의 비밀 유지를 서약하는 서류",
        "aliases": ["보안 서약서", "비밀유지서약서", "비밀유지 서약서", "정보보안서약서", "NDA"],
        "definition": {
            "title": "보 안 서 약 서",
            "table": [
                ["계 약 명", "contract_title"],
                ["계약기간", "period"],
                ["소    속", "company_name"],
                ["성    명", "representative"],
            ],
            "body": (
                "본인은 「{contract_title}」 수행과 관련하여 다음 사항을 준수할 것을 서약합니다.\n"
                "1. 과업 수행 중 알게 된 {client_name}의 업무상 비밀과 개인정보를 외부에 누설하지 않는다.\n"
                "2. 제공받은 자료는 과업 목적 외로 사용하지 않으며, 과업 종료 시 즉시 반납·파기한다.\n"
                "3. 위 사항을 위반할 경우 관련 법령 및 계약 조건에 따른 책임을 진다."
            ),
            "signature": SIGN_BLOCK,
            "recipient": "{client_name} 귀하",
        },
        "required": ["contract_title", "company_name", "representative", "client_name"],
    },
    {
        "key": "seal_registration",
        "name": "사용인감계",
        "category": "인감·확인",
        "description": "계약 업무에 사용할 인감을 신고하는 서류",
        "aliases": ["사용인감 신고서", "인감신고서", "사용 인감계"],
        "definition": {
            "title": "사 용 인 감 계",
            "table": [
                ["상    호", "company_name"],
                ["대 표 자", "representative"],
                ["사업자등록번호", "business_number"],
                ["주    소", "address"],
                ["사용 용도", "contract_title"],
            ],
            "body": "위 인감을 「{contract_title}」 계약과 관련한 제반 서류에 사용하고자 신고합니다.",
            "signature": SIGN_BLOCK,
            "recipient": "{client_name} 귀하",
        },
        "required": ["company_name", "representative", "business_number", "contract_title"],
    },
    {
        "key": "work_plan",
        "name": "과업수행계획서",
        "category": "착수·완료",
        "description": "과업 개요·기간·수행 방안을 정리한 계획서 (개요 문장은 AI가 작성)",
        "aliases": ["수행계획서", "사업수행계획서", "과업 수행 계획서", "작업계획서"],
        "definition": {
            "title": "과 업 수 행 계 획 서",
            "table": [
                ["계 약 명", "contract_title"],
                ["발 주 처", "client_name"],
                ["수행업체", "company_name"],
                ["수행기간", "period"],
                ["사업책임자", "manager_name"],
                ["과업 내용", "description"],
                ["과업 개요", "work_summary"],
            ],
            "body": "상기와 같이 과업을 수행하고자 계획서를 제출합니다.",
            "signature": SIGN_BLOCK,
        },
        "required": ["contract_title", "client_name", "company_name", "period", "description"],
    },
    {
        "key": "confirmation",
        "name": "확인서",
        "category": "인감·확인",
        "description": "계약 사실 및 기재 내용이 사실과 다름없음을 확인하는 범용 확인서",
        "aliases": ["사실확인서", "계약사실확인서", "각종 확인서"],
        "definition": {
            "title": "확  인  서",
            "table": [
                ["계 약 명", "contract_title"],
                ["계약금액", "amount"],
                ["계약기간", "period"],
                ["상    호", "company_name"],
                ["대 표 자", "representative"],
            ],
            "body": "위 기재 내용이 사실과 다름없음을 확인합니다.",
            "signature": SIGN_BLOCK,
            "recipient": "{client_name} 귀하",
        },
        "required": ["contract_title", "company_name", "representative"],
    },
]

_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def template_field_keys(definition: dict) -> list[str]:
    """정의에서 쓰이는 모든 표준 필드 키 (순서 유지, 중복 제거)."""
    keys: list[str] = [k for _, k in definition.get("table", [])]
    for part in (definition.get("body", ""), definition.get("recipient", "")):
        keys += _PLACEHOLDER.findall(part)
    if definition.get("signature"):
        keys += ["submit_date", "company_name", "address", "representative"]
    seen, out = set(), []
    for k in keys:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def fill_text(text: str, values: dict) -> str:
    return _PLACEHOLDER.sub(lambda m: str(values.get(m.group(1), "") or f"[{m.group(1)}]"), text)


# The original compact definitions above are retained for migration history.
# Runtime imports use the upgraded native-document definitions below.
from app.professional_templates import (  # noqa: E402,F401
    BUILTIN_TEMPLATES as BUILTIN_TEMPLATES,
    fill_text as fill_text,
    template_field_keys as template_field_keys,
)
