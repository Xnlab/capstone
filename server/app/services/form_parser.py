"""기업 자체 양식(한글/Word/PDF) 구조 분석 (3주차 CASE 2).

양식에서 '항목명 + 빈 칸' 구조를 찾아 입력 위치 후보를 뽑는다.
- DOCX 표: [항목명 셀][빈 셀] → 빈 셀이 입력 위치
- DOCX 문단: "항목명 :  ____" → 콜론 뒤가 입력 위치
- PDF: 텍스트 줄 단위로 "항목명 :" 패턴 추출 (PDF는 원본 편집이 어려워 결과는 새 Word로 재구성)
"""

import re
from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader

_LABEL_OK = re.compile(r"^[가-힣A-Za-z\s()·ㆍ/\-\.]{2,25}$")
_PARA_FIELD = re.compile(r"^\s*(?P<label>[가-힣A-Za-z\s()·ㆍ/]{2,25}?)\s*[:：]\s*(?P<blank>[_\s\.]*)$")
_BLANK = re.compile(r"^[\s_\.\-]*$")


def _is_label(text: str) -> bool:
    t = text.strip()
    return bool(t) and bool(_LABEL_OK.match(t)) and not t.endswith(("다.", "함.", "음."))


def _unique_cells(row):
    seen, out = set(), []
    for idx, c in enumerate(row.cells):
        if id(c._tc) in seen:
            continue
        seen.add(id(c._tc))
        out.append((idx, c))
    return out


def analyze_docx(path: Path) -> dict:
    doc = DocxDocument(str(path))
    items: list[dict] = []
    for ti, table in enumerate(doc.tables):
        for ri, row in enumerate(table.rows):
            cells = _unique_cells(row)
            row_text = " | ".join(c.text.strip() for _, c in cells)
            for (ci, cell), (nci, ncell) in zip(cells, cells[1:]):
                if _is_label(cell.text) and _BLANK.match(ncell.text):
                    items.append({
                        "label": re.sub(r"\s+", " ", cell.text.strip()),
                        "context": row_text,
                        "location": {"type": "cell", "table": ti, "row": ri, "col": nci},
                    })
    for pi, p in enumerate(doc.paragraphs):
        m = _PARA_FIELD.match(p.text)
        if m:
            items.append({
                "label": m.group("label").strip(),
                "context": p.text.strip(),
                "location": {"type": "para", "index": pi},
            })
    title = next((p.text.strip() for p in doc.paragraphs if p.text.strip()), "")
    return {"title": title[:60], "items": items, "paragraphs": len(doc.paragraphs), "tables": len(doc.tables)}


def analyze_pdf(path: Path) -> dict:
    reader = PdfReader(str(path))
    lines: list[str] = []
    for page in reader.pages:
        lines += [ln for ln in (page.extract_text() or "").splitlines() if ln.strip()]
    items = []
    for li, ln in enumerate(lines):
        m = _PARA_FIELD.match(ln)
        if m:
            items.append({"label": m.group("label").strip(), "context": ln.strip(), "location": {"type": "pdf_line", "index": li}})
            continue
        # "계약명 계약금액" 처럼 항목명만 나열된 짧은 줄
        t = ln.strip()
        if _is_label(t) and len(t) <= 12:
            items.append({"label": re.sub(r"\s+", " ", t), "context": t, "location": {"type": "pdf_line", "index": li}})
    title = lines[0].strip()[:60] if lines else ""
    return {"title": title, "items": items, "lines": lines[:200], "pages": len(reader.pages)}


def analyze(path: Path, file_type: str) -> dict:
    if file_type == "docx":
        return analyze_docx(path)
    if file_type == "pdf":
        return analyze_pdf(path)
    if file_type == 'hwpx':
        from app.services.hwpx_forms import analyze as analyze_hwpx
        return analyze_hwpx(path)
    raise ValueError("지원하지 않는 형식입니다. (docx, pdf, hwp, hwpx)")
