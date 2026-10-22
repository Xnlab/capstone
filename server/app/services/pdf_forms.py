"""Fill reviewed rectangles without rebuilding the original PDF layout."""
import base64
import math
import re
from pathlib import Path

import pymupdf
from fastapi import HTTPException

from app.core.config import settings


def positioned(template):
    return template.source_type == "pdf" and bool(template.fields) and all(
        f.get("location", {}).get("type") == "pdf_rect" for f in template.fields
    )


def validate_locations(template):
    if not template.source_path or not Path(template.source_path).is_file():
        raise HTTPException(409, "원본 PDF가 없습니다. 다시 등록해 주세요.")
    with pymupdf.open(template.source_path) as doc:
        for page in doc:
            if page.rotation or any(a.type[0] == pymupdf.PDF_ANNOT_REDACT for a in (page.annots() or [])):
                raise HTTPException(422, "회전 또는 삭제 주석이 있는 PDF는 원본을 정리한 뒤 등록하세요.")
        for field in template.fields:
            loc = field.get("location", {})
            page_index, coordinates = loc.get("page"), loc.get("rect")
            if type(page_index) is not int or not 0 <= page_index < len(doc):
                raise HTTPException(422, "PDF 입력 페이지가 올바르지 않습니다.")
            if not isinstance(coordinates, list) or len(coordinates) != 4 or not all(type(n) in (int, float) and math.isfinite(n) for n in coordinates):
                raise HTTPException(422, "PDF 입력 영역은 유한한 좌표 4개여야 합니다.")
            rect, page = pymupdf.Rect(coordinates), doc[page_index]
            if rect.is_empty or not page.rect.contains(rect):
                raise HTTPException(422, "PDF 입력 영역이 페이지를 벗어났습니다.")
            # Some HWP-generated PDFs encode blank padding as control glyphs;
            # get_textbox turns these into replacement characters. Inspect raw chars.
            chars = [char["c"] for block in page.get_text("rawdict")["blocks"]
                     for line in block.get("lines", []) for span in line["spans"]
                     for char in span["chars"] if rect.intersects(pymupdf.Rect(char["bbox"]))]
            existing = re.sub(r"[\s\x00-\x1f]+", "", "".join(chars))
            if loc.get("replace"):
                if field.get("field_key") != "submit_date" or re.sub(r"[\d년월일.\-/_]", "", existing):
                    raise HTTPException(422, "날짜 입력란 외의 원본 문구는 지울 수 없습니다.")
            elif existing:
                raise HTTPException(422, f"'{field['label']}' 입력 영역이 원본 문구와 겹칩니다.")
        for i, field in enumerate(template.fields):
            for other in template.fields[i + 1:]:
                a, b = field["location"], other["location"]
                if a["page"] == b["page"] and pymupdf.Rect(a["rect"]).intersects(pymupdf.Rect(b["rect"])):
                    raise HTTPException(422, "PDF 입력 영역끼리 겹칩니다.")


def fill_pdf(template, values):
    validate_locations(template)
    font_path = Path(settings.PDF_FONT_PATH)
    if not font_path.is_file():
        raise HTTPException(503, "PDF 입력에 사용할 한글 글꼴을 설정해 주세요.")
    with pymupdf.open(template.source_path) as doc:
        for field in template.fields:
            loc = field["location"]
            if loc.get("replace") and str(values.get(field["field_key"], "")).strip():
                doc[loc["page"]].add_redact_annot(pymupdf.Rect(loc["rect"]), fill=(1, 1, 1))
        for page in doc:
            if page.first_annot:
                page.apply_redactions(images=0, graphics=0)
        for field in template.fields:
            text = str(values.get(field["field_key"], "") or "")
            if not text:
                continue
            loc = field["location"]
            page = doc[loc["page"]]
            page.insert_font(fontname="FormKorean", fontfile=str(font_path))
            for size in (11, 10, 9, 8, 7, 6):
                remaining = page.insert_textbox(pymupdf.Rect(loc["rect"]), text, fontname="FormKorean", fontsize=size, color=(0, 0, 0))
                if remaining >= 0:
                    break
            else:
                raise HTTPException(422, f"'{field['label']}' 값이 입력 칸보다 깁니다. 내용을 줄여 주세요.")
        return doc.tobytes(garbage=4, deflate=True)


def preview_html(data):
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        images = []
        for page in doc:
            image = base64.b64encode(page.get_pixmap(matrix=pymupdf.Matrix(1.2, 1.2), alpha=False).tobytes("png")).decode("ascii")
            images.append(f'<img alt="작성된 양식 {page.number + 1}페이지" style="width:100%;height:auto" src="data:image/png;base64,{image}" />')
        return "\n".join(images)
