"""Reviewed input coordinates for public, project-specific G2B originals.

Coordinates use PDF points; source page numbers are zero-based.
Seals and signatures intentionally remain blank.
"""


def field(label, key, rect, replace=False):
    return {"label": label, "field_key": key, "confidence": 1, "method": "user", "context": "원본 PDF와 대조하여 입력 위치 확인", "location": {"type": "pdf_rect", "page": 0, "rect": rect, "replace": replace}}


FOURNATURES_URL = "https://www.g2b.go.kr/pn/pnp/pnpe/UntyAtchFile/downloadFile.do?bidPbancNo=R25BK00976607&bidPbancOrd=000&fileSeq=1&fileType="
SCNG_URL = "https://www.g2b.go.kr/pn/pnp/pnpe/UntyAtchFile/downloadFile.do?bidPbancNo=R25BK01032428&bidPbancOrd=000&fileSeq=1&fileType="

FORMS = [
    {"key": "g2b-2025-fournatures-seal", "file": "fournatures-seal", "bundle": "fournatures.pdf", "page": 14,
     "name": "포네이처스 사용인감계 (2025 공고)", "organization": "주식회사 포네이처스", "document_type": "사용인감계", "project_code": "R25BK00976607", "source_url": FOURNATURES_URL,
     "fields": [field("업체명", "company_name", [287, 248, 514, 271]), field("주소", "address", [287, 278, 514, 301]), field("대표자", "representative", [287, 308, 514, 331]),
                field("제출일", "submit_date", [231, 560, 374, 584], True), field("서명란 주소", "address", [254, 620, 538, 643]), field("서명란 업체명", "company_name", [254, 653, 538, 676]), field("서명란 대표자", "representative", [254, 686, 448, 709])]},
    {"key": "g2b-2025-fournatures-pledge", "file": "fournatures-pledge", "bundle": "fournatures.pdf", "page": 10,
     "name": "포네이처스 입찰 서약서 (2025 공고)", "organization": "주식회사 포네이처스", "document_type": "서약서", "project_code": "R25BK00976607", "source_url": FOURNATURES_URL,
     "fields": [field("주소", "address", [229, 220, 536, 243]), field("상호", "company_name", [229, 247, 536, 270]), field("대표자", "representative", [229, 274, 536, 297]),
                field("제출일", "submit_date", [225, 588, 378, 612], True), field("서명란 대표자", "representative", [328, 643, 421, 666])]},
    {"key": "g2b-2025-scng-security", "file": "scng-security", "bundle": "scng.pdf", "page": 9,
     "name": "서울씨엔지 보안각서 (2025 공고)", "organization": "주식회사 서울씨엔지", "document_type": "보안각서", "project_code": "R25BK01032428", "source_url": SCNG_URL,
     "fields": [field("제출일", "submit_date", [231, 453, 377, 476], True), field("업체명", "company_name", [348, 522, 546, 545]), field("주소", "address", [348, 557, 546, 585]), field("대표자", "representative", [348, 592, 448, 615])]},
]
