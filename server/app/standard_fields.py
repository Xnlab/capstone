"""내부 표준 데이터(표준 필드 사전).

기업마다 다른 항목명("총 용역대금", "지급 예정 금액", "용역 수행비")을
하나의 표준 키(amount)로 모으는 기준. 양식 분석·자동 작성·교차 검증이 모두 이 사전을 쓴다.
"""

from datetime import date

# key: (한글명, 그룹, 동의어 목록)
STANDARD_FIELDS: dict[str, dict] = {
    # 회사 정보
    "company_name": {"label": "회사명", "group": "company", "synonyms": ["상호", "업체명", "회사명", "법인명", "수급인", "계약상대자", "용역업체", "공급자 상호", "사업자명"]},
    "representative": {"label": "대표자명", "group": "company", "synonyms": ["대표자", "대표이사", "대표자 성명", "대표", "성명(대표자)"]},
    "business_number": {"label": "사업자등록번호", "group": "company", "synonyms": ["사업자번호", "사업자 등록번호", "등록번호"]},
    "address": {"label": "주소", "group": "company", "synonyms": ["소재지", "사업장 주소", "본점 소재지", "주소지"]},
    "phone": {"label": "연락처", "group": "company", "synonyms": ["전화번호", "전화", "대표번호", "연락처", "TEL"]},
    "email": {"label": "이메일", "group": "company", "synonyms": ["전자우편", "이메일 주소", "E-mail", "메일"]},
    "manager_name": {"label": "담당자", "group": "company", "synonyms": ["담당자명", "실무 담당자", "책임자", "현장대리인", "사업책임자"]},
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
    # AI 생성 문장
    "work_summary": {"label": "과업 개요(AI)", "group": "ai", "synonyms": ["과업 개요", "수행 개요", "추진 개요"]},
}

MONEY_FIELDS = {"amount", "supply_amount", "vat"}
DATE_FIELDS = {"start_date", "end_date", "submit_date"}
# 교차 검증 대상: 여러 서류에 반복 등장하므로 값이 모두 같아야 하는 필드
CONSISTENCY_FIELDS = ["company_name", "representative", "business_number", "contract_title", "client_name", "amount", "period", "start_date", "end_date"]


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
    }
    return vals
