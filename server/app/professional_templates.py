"""Professional built-in templates used for native HWPX/XLSX output."""

import re


def info(*rows):
    return {"type": "info", "rows": [list(row) for row in rows]}


def paragraph(text: str):
    return {"type": "paragraph", "text": text}


def field_block(label: str, key: str):
    return {"type": "field_block", "label": label, "key": key}


def attachments(*items):
    return {"type": "attachments", "items": list(items)}


def definition(title, fields, sections, required, *, output="hwpx", signature=True, recipient=None, layout="formal"):
    out = {
        "layout": layout,
        "output_format": output,
        "title": title,
        "fields": fields,
        "sections": sections,
        "required": required,
    }
    if signature:
        out["signature"] = True
    if recipient:
        out["recipient"] = recipient
    return out


BUILTIN_TEMPLATES: list[dict] = [
    {
        "key": "quotation", "name": "견적서", "category": "계약·금액",
        "description": "품목별 수량·단가·공급가액·세액이 자동 계산되는 실무형 Excel 견적서",
        "aliases": ["견적", "가격견적서", "견적 내역", "견적서류"],
        "definition": definition(
            "견 적 서",
            ["contract_title", "client_name", "company_name", "business_number", "representative", "address", "phone", "business_type", "business_item", "submit_date", "quote_items", "supply_amount", "vat", "amount", "amount_korean"],
            [
                info(("프로젝트명", "contract_title"), ("수신자", "client_name"), ("공급자", "company_name"), ("사업자등록번호", "business_number"), ("대표자", "representative"), ("작성일자", "submit_date")),
                {"type": "line_items", "key": "quote_items", "mode": "quotation"},
            ],
            ["contract_title", "client_name", "company_name", "business_number", "representative", "quote_items", "amount"],
            output="xlsx", signature=False, layout="quotation",
        ),
    },
    {
        "key": "cost_breakdown", "name": "산출내역서", "category": "계약·금액",
        "description": "세부 항목과 공급가액·부가세·총액을 갖춘 계약금액 산출내역서",
        "aliases": ["산출 내역서", "낙찰금액 산출내역서", "원가계산서", "비용산출서", "세부산출내역서"],
        "definition": definition(
            "계 약 금 액  산 출 내 역 서",
            ["contract_title", "client_name", "company_name", "business_number", "representative", "submit_date", "detail_items", "supply_amount", "vat", "amount", "amount_korean", "address"],
            [
                info(("계약명", "contract_title"), ("발주처", "client_name"), ("수행업체", "company_name"), ("작성일", "submit_date")),
                {"type": "line_items", "key": "detail_items", "mode": "cost"},
                paragraph("상기 금액은 계약 목적 달성에 필요한 직접비·제경비 및 기술료 등을 포함한 금액입니다."),
            ],
            ["contract_title", "company_name", "detail_items", "supply_amount", "vat", "amount"], recipient="{client_name} 귀하",
        ),
    },
    {
        "key": "commencement", "name": "착수계", "category": "착수·완료",
        "description": "계약명·금액·계약일·착수일·완료기한과 제출인 정보를 갖춘 착수 신고서",
        "aliases": ["착수신고서", "착수 신고서", "착수보고", "착공계"],
        "definition": definition(
            "착  수  계",
            ["contract_title", "amount", "contract_date", "start_date", "end_date", "work_summary", "submit_date", "company_name", "representative", "address", "client_name"],
            [
                info(("계 약 명", "contract_title"), ("계약금액", "amount"), ("계약일자", "contract_date"), ("착수일자", "start_date"), ("완료기한", "end_date")),
                field_block("과업 개요", "work_summary"),
                paragraph("위 계약에 따라 {start_date}부로 과업에 착수하였기에 착수계를 제출합니다."),
                attachments("과업수행계획서 1부", "보안서약서 1부", "사용인감계 1부"),
            ],
            ["contract_title", "amount", "start_date", "end_date", "company_name", "representative", "client_name"], recipient="{client_name} 귀하",
        ),
    },
    {
        "key": "work_plan", "name": "과업수행계획서", "category": "착수·완료",
        "description": "과업 개요·추진 방법·일정·책임자를 정리한 계약 착수용 수행계획서",
        "aliases": ["수행계획서", "사업수행계획서", "과업 수행 계획서", "작업계획서"],
        "definition": definition(
            "과 업 수 행 계 획 서",
            ["contract_title", "client_name", "company_name", "period", "manager_name", "description", "work_summary", "work_method", "work_schedule", "submit_date", "representative", "address"],
            [
                info(("계 약 명", "contract_title"), ("발 주 처", "client_name"), ("수행업체", "company_name"), ("수행기간", "period"), ("책 임 자", "manager_name")),
                field_block("1. 과업 목적 및 개요", "work_summary"), field_block("2. 주요 과업 내용", "description"),
                field_block("3. 수행 방법", "work_method"), field_block("4. 추진 일정", "work_schedule"),
                paragraph("상기와 같이 과업수행계획서를 제출합니다."),
            ],
            ["contract_title", "client_name", "company_name", "period", "description", "work_method", "work_schedule"], recipient="{client_name} 귀하",
        ),
    },
    {
        "key": "completion", "name": "완료계·준공계", "category": "착수·완료",
        "description": "계약 완료 사실과 완료내역을 함께 제출하는 완료계(준공계)",
        "aliases": ["완료계", "준공계", "완료신고서", "용역완료계", "준공신고서", "완료내역서"],
        "definition": definition(
            "완  료  계",
            ["contract_title", "amount", "amount_korean", "contract_date", "start_date", "end_date", "completion_details", "detail_items", "submit_date", "company_name", "representative", "address", "client_name"],
            [
                info(("계 약 명", "contract_title"), ("계약금액", "amount_korean"), ("계약일자", "contract_date"), ("착수일자", "start_date"), ("완료일자", "end_date")),
                field_block("완료 내용", "completion_details"), {"type": "line_items", "key": "detail_items", "mode": "completion"},
                paragraph("상기와 같이 계약 과업을 완료하였기에 완료계를 제출합니다."),
            ],
            ["contract_title", "amount", "end_date", "completion_details", "company_name", "representative"], recipient="{client_name} 귀하",
        ),
    },
    {
        "key": "security_pledge", "name": "보안서약서", "category": "보안·서약",
        "description": "과업자료·개인정보·성과물의 비밀유지와 반납·파기를 약정하는 보안서약서",
        "aliases": ["보안 서약서", "비밀유지서약서", "비밀유지 서약서", "정보보안서약서", "NDA", "보안각서"],
        "definition": definition(
            "보 안 서 약 서",
            ["contract_title", "period", "company_name", "representative", "client_name", "submit_date", "address"],
            [
                info(("계 약 명", "contract_title"), ("계약기간", "period"), ("소 속", "company_name"), ("성 명", "representative")),
                paragraph("본인은 「{contract_title}」 수행과 관련하여 다음 사항을 성실히 준수할 것을 서약합니다."),
                {"type": "numbered", "items": [
                    "과업 수행 중 알게 된 업무상 비밀과 개인정보를 외부에 누설하거나 목적 외로 이용하지 않는다.",
                    "발주처가 제공한 자료와 계정은 승인된 업무에만 사용하고 제3자에게 제공하지 않는다.",
                    "성과물과 작업자료를 무단 복제·반출하지 않으며 계약 종료 시 지시에 따라 반납 또는 파기한다.",
                    "보안사고가 발생하거나 우려가 있을 때 즉시 발주처에 알리고 필요한 조치에 협조한다.",
                    "위 사항을 위반한 경우 관련 법령과 계약조건에 따른 책임을 부담한다.",
                ]},
            ],
            ["contract_title", "company_name", "representative", "client_name"], recipient="{client_name} 귀하",
        ),
    },
    {
        "key": "seal_registration", "name": "사용인감계", "category": "인감·확인",
        "description": "계약 업무에 사용할 인감과 법적 책임을 신고하는 사용인감계",
        "aliases": ["사용인감 신고서", "인감신고서", "사용 인감계"],
        "definition": definition(
            "사 용 인 감 계",
            ["company_name", "representative", "business_number", "address", "contract_title", "client_name", "submit_date"],
            [
                info(("상 호", "company_name"), ("대 표 자", "representative"), ("사업자등록번호", "business_number"), ("주 소", "address"), ("사용 용도", "contract_title")),
                {"type": "stamp_box", "labels": ["법인(개인) 인감", "사용 인감"]},
                paragraph("위 사용인감을 「{contract_title}」 계약과 관련한 계약·청구 및 제반 제출서류에 사용하고, 이로 인하여 발생하는 모든 책임을 부담할 것을 확인합니다."),
                attachments("인감증명서 1부(해당 시)"),
            ],
            ["company_name", "representative", "business_number", "contract_title", "client_name"], recipient="{client_name} 귀하",
        ),
    },
    {
        "key": "advance_request", "name": "선급금 지급 요청서", "category": "청구·정산",
        "description": "계약정보·신청금액·계좌·사용목적과 첨부서류를 갖춘 선금 지급 신청서",
        "aliases": ["선금 신청서", "선급금 신청서", "선금급 신청서", "선지급 요청서", "선금 지급 요청 공문"],
        "definition": definition(
            "선 금 지 급 신 청 서",
            ["document_number", "submit_date", "contract_number", "contract_date", "contract_title", "amount", "period", "advance_amount", "bank_name", "account_number", "account_holder", "usage_purpose", "company_name", "business_number", "representative", "phone", "address", "client_name"],
            [
                info(("문서번호", "document_number"), ("시행일자", "submit_date"), ("계약번호", "contract_number"), ("계약일자", "contract_date"), ("계약건명", "contract_title"), ("계약금액", "amount"), ("계약기간", "period"), ("선금 신청금액", "advance_amount"), ("거래은행", "bank_name"), ("계좌번호", "account_number"), ("예금주", "account_holder"), ("사용목적", "usage_purpose")),
                paragraph("위 계약을 성실히 이행할 것을 확약하며 관련 계약조건에 따라 상기와 같이 선금 지급을 신청합니다."),
                attachments("선금신청 각서 1부", "선금사용계획서 1부", "납세증명서 각 1부", "선금급 보증보험증권 1부"),
            ],
            ["contract_title", "amount", "advance_amount", "bank_name", "account_number", "account_holder", "company_name", "representative"], recipient="{client_name} 귀하",
        ),
    },
    {
        "key": "payment_request", "name": "비용·대금 지급 요청서", "category": "청구·정산",
        "description": "완료 후 청구금액과 입금계좌를 제출하는 대금청구서",
        "aliases": ["대금청구서", "비용지급 신청서", "비용 지급 요청서", "대금 지급 요청서", "청구서", "송금의뢰서"],
        "definition": definition(
            "대 금 청 구 서",
            ["contract_title", "amount", "payment_amount", "payment_amount_korean", "bank_name", "account_number", "account_holder", "company_name", "business_number", "representative", "address", "phone", "client_name", "submit_date"],
            [
                info(("건 명", "contract_title"), ("계약금액", "amount"), ("청구금액", "payment_amount_korean"), ("상 호", "company_name"), ("사업자등록번호", "business_number"), ("대표자", "representative")),
                paragraph("위 금액을 청구하오니 아래 계좌로 송금하여 주시기 바랍니다."),
                {"type": "bank", "rows": [["거래은행", "bank_name"], ["계좌번호", "account_number"], ["예금주", "account_holder"]]},
                attachments("전자세금계산서 1부", "통장사본 1부", "완납증명서 각 1부(요청 시)"),
            ],
            ["contract_title", "payment_amount", "bank_name", "account_number", "account_holder", "company_name", "representative"], recipient="{client_name} 귀하",
        ),
    },
]


_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def template_field_keys(definition: dict) -> list[str]:
    if definition.get("fields"):
        return list(dict.fromkeys(definition["fields"]))
    keys: list[str] = [k for _, k in definition.get("table", [])]
    for part in (definition.get("body", ""), definition.get("recipient", "")):
        keys += _PLACEHOLDER.findall(part)
    if definition.get("signature"):
        keys += ["submit_date", "company_name", "address", "representative"]
    return list(dict.fromkeys(keys))


def fill_text(text: str, values: dict) -> str:
    return _PLACEHOLDER.sub(lambda m: str(values.get(m.group(1), "") or f"[{m.group(1)}]"), text)
