"""내부 표준 데이터(표준 필드 사전).

기업마다 다른 항목명("총 용역대금", "지급 예정 금액", "용역 수행비")을
하나의 표준 키(amount)로 모으는 기준. 양식 분석·자동 작성·교차 검증이 모두 이 사전을 쓴다.
"""

from datetime import date

# key: (한글명, 그룹, 동의어 목록)
STANDARD_FIELDS: dict[str, dict] = {
    "staff_plan": {"label": "참여인력 및 역할", "group": "document", "synonyms": ["참여인력", "업무분장"]},
    "deliverables": {"label": "제출 산출물 및 납품 일정", "group": "document", "synonyms": ["성과품", "납품목록"]},
    "quality_plan": {"label": "품질·보안 및 보고 계획", "group": "document", "synonyms": ["품질관리계획", "보고계획"]},
    "attachment_list": {"label": "첨부서류 목록", "group": "document", "synonyms": ["붙임", "첨부목록"]},
    # 회사 정보
    "company_name": {"label": "회사명", "group": "company", "synonyms": ["상호", "업체명", "회사명", "법인명", "수급인", "계약상대자", "용역업체", "공급자 상호", "사업자명"]},
    "representative": {"label": "대표자명", "group": "company", "synonyms": ["대표자", "대표이사", "대표자 성명", "대표", "성명(대표자)"]},
    "business_number": {"label": "사업자등록번호", "group": "company", "synonyms": ["사업자번호", "사업자 등록번호", "등록번호"]},
    "address": {"label": "주소", "group": "company", "synonyms": ["소재지", "사업장 주소", "본점 소재지", "주소지"]},
    "phone": {"label": "연락처", "group": "company", "synonyms": ["전화번호", "전화", "대표번호", "연락처", "TEL"]},
    "email": {"label": "이메일", "group": "company", "synonyms": ["전자우편", "이메일 주소", "E-mail", "메일"]},
    "manager_name": {"label": "담당자", "group": "company", "synonyms": ["담당자명", "실무 담당자", "책임자", "현장대리인", "사업책임자"]},
    "business_type": {"label": "업태", "group": "company", "synonyms": ["업 태", "사업자 업태"]},
    "business_item": {"label": "종목", "group": "company", "synonyms": ["업종", "업 종", "사업자 종목"]},
    "bank_name": {"label": "거래은행", "group": "company", "synonyms": ["은행명", "거래 은행"]},
    "account_number": {"label": "계좌번호", "group": "company", "synonyms": ["입금계좌", "계좌 번호"]},
    "account_holder": {"label": "예금주", "group": "company", "synonyms": ["통장명의", "예금주명"]},
    # 계약 정보
    "contract_title": {"label": "계약명", "group": "contract", "synonyms": ["용역명", "사업명", "과업명", "건명", "계약건명", "프로젝트명"]},
    "client_name": {"label": "발주처", "group": "contract", "synonyms": ["발주기관", "계약기관", "수요기관", "도급인", "갑", "발주자"]},
    "amount": {"label": "계약금액", "group": "contract", "synonyms": ["총 용역대금", "지급 예정 금액", "용역 수행비", "계약 금액", "총액", "용역대금", "총 계약금액", "견적금액", "합계금액"]},
    "amount_korean": {"label": "계약금액(한글)", "group": "derived", "synonyms": ["금액(한글)", "일금"]},
    "supply_amount": {"label": "공급가액", "group": "derived", "synonyms": ["공급가", "공급 가액"]},
    "vat": {"label": "부가세", "group": "derived", "synonyms": ["부가가치세", "세액", "VAT"]},
    "start_date": {"label": "착수일", "group": "contract", "synonyms": ["착수일자", "계약 시작일", "시작일", "착수 연월일", "개시일"]},
    "end_date": {"label": "완료일", "group": "contract", "synonyms": ["준공일", "완료 예정일", "종료일", "준공 예정일", "완료일자"]},
    "period": {"label": "계약기간", "group": "derived", "synonyms": ["수행기간", "용역기간", "계약 기간", "과업기간", "사업기간"]},
    "description": {"label": "업무내용", "group": "contract", "synonyms": ["과업내용", "용역내용", "사업내용", "주요 내용", "과업 범위"]},
    "submit_date": {"label": "제출일", "group": "derived", "synonyms": ["작성일", "일자", "신청일", "제출일자", "작성일자"]},
    "contract_date": {"label": "계약일자", "group": "contract", "synonyms": ["계약일", "계약 체결일"]},
    "contract_number": {"label": "계약번호", "group": "contract", "synonyms": ["계약 번호"]},
    "document_number": {"label": "문서번호", "group": "document", "synonyms": ["문서 번호", "시행문서번호"]},
    "advance_amount": {"label": "선금 신청금액", "group": "document", "synonyms": ["선금신청금액", "선급금", "선금액"]},
    "payment_amount": {"label": "청구금액", "group": "document", "synonyms": ["대금청구액", "정산금액", "지급 요청금액"]},
    "payment_amount_korean": {"label": "청구금액(한글)", "group": "derived", "synonyms": ["청구금액 한글", "일금"]},
    "usage_purpose": {"label": "사용목적", "group": "document", "synonyms": ["선금 사용목적", "용도"]},
    "quote_items": {"label": "견적 품목", "group": "document", "synonyms": ["견적내역", "품목내역"]},
    "detail_items": {"label": "세부 산출내역", "group": "document", "synonyms": ["완료내역", "산출 세부내역"]},
    "completion_details": {"label": "완료 내용", "group": "document", "synonyms": ["완료내역", "수행결과"]},
    "work_method": {"label": "수행 방법", "group": "document", "synonyms": ["과업수행방법", "추진방법"]},
    "work_schedule": {"label": "추진 일정", "group": "document", "synonyms": ["수행일정", "과업일정", "일정계획"]},
    "activity_date": {"label": "활동일자", "group": "document", "synonyms": ["활동일", "일시"]},
    "activity_time": {"label": "활동시간", "group": "document", "synonyms": ["활동 시간", "시간"]},
    "activity_place": {"label": "활동장소", "group": "document", "synonyms": ["장소", "활동 장소"]},
    "attendees": {"label": "참석자", "group": "document", "synonyms": ["참석인원", "참여자"]},
    "activity_topic": {"label": "활동주제", "group": "document", "synonyms": ["주제", "회의주제"]},
    "activity_details": {"label": "주요 활동내용", "group": "document", "synonyms": ["활동내용", "주요내용"]},
    "activity_result": {"label": "활동 결과 및 향후 계획", "group": "document", "synonyms": ["활동결과", "향후계획", "성과"]},
    # AI 생성 문장
    "work_summary": {"label": "과업 개요(AI)", "group": "ai", "synonyms": ["과업 개요", "수행 개요", "추진 개요"]},
}

MONEY_FIELDS = {"amount", "supply_amount", "vat", "advance_amount", "payment_amount"}
DATE_FIELDS = {"contract_date", "start_date", "end_date", "submit_date"}
# 교차 검증 대상: 여러 서류에 반복 등장하므로 값이 모두 같아야 하는 필드
CONSISTENCY_FIELDS = ["company_name", "representative", "business_number", "contract_title", "client_name", "amount", "period", "contract_date", "start_date", "end_date"]


def field_label(key: str) -> str:
    return STANDARD_FIELDS.get(key, {}).get("label", key)


_DIGITS = "영일이삼사오육칠팔구"
_SMALL = ["", "십", "백", "천"]
_BIG = ["", "만", "억", "조"]


def korean_amount(n: int) -> str:
    """50000000 -> '일금 오천만원정'"""
    if n <= 0:
        return "일금 영원정"
    parts, idx = [], 0
    while n > 0:
        chunk, n = n % 10000, n // 10000
        if chunk:
            s = ""
            for i, ch in enumerate(reversed(f"{chunk:04d}")):
                d = int(ch)
                if d:
                    s = (("" if d == 1 and i > 0 else _DIGITS[d]) + _SMALL[i]) + s
            parts.append(s + _BIG[idx])
        idx += 1
    return "일금 " + "".join(reversed(parts)) + "원정"


def fmt_money(n: int | str | None) -> str:
    try:
        return f"{int(n):,}원"
    except (TypeError, ValueError):
        return str(n or "")


def fmt_date(d: date | str | None) -> str:
    if not d:
        return ""
    if isinstance(d, str):
        return d
    return d.strftime("%Y. %m. %d.")


def base_values(company, contract) -> dict:
    """회사·계약정보로부터 표준 필드 값을 계산 (파생값 포함). 값은 모두 사람이 읽는 문자열."""
    amount = contract.amount or 0
    supply = round(amount / 1.1) if amount else 0
    vals = {
        "company_name": getattr(company, "company_name", "") or "",
        "representative": getattr(company, "representative", "") or "",
        "business_number": getattr(company, "business_number", "") or "",
        "address": getattr(company, "address", "") or "",
        "phone": getattr(company, "phone", "") or "",
        "email": getattr(company, "email", "") or "",
        "manager_name": getattr(company, "manager_name", "") or "",
        "business_type": getattr(company, "business_type", "") or "",
        "business_item": getattr(company, "business_item", "") or "",
        "bank_name": getattr(company, "bank_name", "") or "",
        "account_number": getattr(company, "account_number", "") or "",
        "account_holder": getattr(company, "account_holder", "") or "",
        "contract_title": contract.contract_title or "",
        "client_name": contract.client_name or "",
        "amount": fmt_money(amount) if amount else "",
        "amount_korean": korean_amount(amount) if amount else "",
        "supply_amount": fmt_money(supply) if amount else "",
        "vat": fmt_money(amount - supply) if amount else "",
        "start_date": fmt_date(contract.start_date),
        "end_date": fmt_date(contract.end_date),
        "period": f"{fmt_date(contract.start_date)} ~ {fmt_date(contract.end_date)}" if contract.start_date and contract.end_date else "",
        "description": contract.description or "",
        "submit_date": fmt_date(date.today()),
        "contract_date": fmt_date(contract.contract_date),
        "contract_number": "",
        "document_number": "",
        "advance_amount": "",
        "payment_amount": fmt_money(amount) if amount else "",
        "payment_amount_korean": korean_amount(amount) if amount else "",
        "usage_purpose": contract.description or "",
        "quote_items": f"{contract.description or contract.contract_title}|1|{supply}|" if amount else "",
        "detail_items": f"{contract.description or contract.contract_title}|1|{supply}|" if amount else "",
        "completion_details": contract.description or "",
        "work_method": "1. 요구사항을 확인하고 세부 수행계획을 확정합니다.\n2. 단계별 과업을 수행하고 진행상황을 공유합니다.\n3. 결과물을 자체 점검한 후 발주처 검수 의견을 반영합니다.",
        "work_schedule": "착수 및 요구사항 분석 → 설계·수행 → 중간점검 → 결과물 제출 및 검수",
        "activity_date": fmt_date(date.today()),
        "activity_time": "",
        "activity_place": "",
        "attendees": "",
        "activity_topic": contract.contract_title or "",
        "activity_details": contract.description or "",
        "activity_result": "",
    }
    return vals
