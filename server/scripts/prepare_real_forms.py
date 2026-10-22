"""Extract official pages and validate original-layout filling before registration.

Run from server/: ../.venv/Scripts/python.exe scripts/prepare_real_forms.py
Download the source URLs in real_form_manifest.py into work/real-forms first.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pymupdf
from pypdf import PdfReader, PdfWriter

from app.models import Template
from app.services.pdf_forms import fill_pdf
from real_form_manifest import FORMS

ROOT = Path(__file__).resolve().parents[2] / "work" / "real-forms"
VALUES = {"company_name": "주식회사 자동작성검증", "representative": "김검증", "address": "대전광역시 유성구 대학로 99", "submit_date": "2026. 10. 22."}


def main():
    results = []
    for spec in FORMS:
        source = ROOT / spec["bundle"]
        reader = PdfReader(source)
        writer = PdfWriter(); writer.add_page(reader.pages[spec["page"]])
        original = ROOT / (spec["file"] + ".pdf")
        writer.write(original)
        template = Template(source_type="pdf", source_path=str(original), fields=spec["fields"])
        filled = fill_pdf(template, VALUES)
        output = ROOT / (spec["file"] + "-filled.pdf")
        output.write_bytes(filled)
        with pymupdf.open(original) as a, pymupdf.open(output) as b:
            assert len(a) == len(b) == 1
            text = b[0].get_text()
            for value in VALUES.values():
                assert value.replace(" ", "") in text.replace(" ", ""), (spec["file"], value)
            for field in spec["fields"]:
                rect = pymupdf.Rect(field["location"]["rect"])
                # Every individual field, including repeated company/address fields, must be filled.
                assert VALUES[field["field_key"]].replace(" ", "") in b[0].get_textbox(rect).replace(" ", "")
            ap, bp = a[0].get_pixmap(alpha=False), b[0].get_pixmap(alpha=False)
            aa = np.frombuffer(ap.samples, dtype=np.uint8).reshape(ap.height, ap.width, 3)
            bb = np.frombuffer(bp.samples, dtype=np.uint8).reshape(bp.height, bp.width, 3)
            mask = np.ones((ap.height, ap.width), dtype=bool)
            for field in spec["fields"]:
                x0, y0, x1, y1 = field["location"]["rect"]
                mask[max(0, int(y0)-3):int(y1)+4, max(0, int(x0)-3):int(x1)+4] = False
            changed = int(np.any(aa != bb, axis=2)[mask].sum())
            # MuPDF may reserialize original text strokes during date redaction.
            # Check fixed text separately, and allow only tiny rasterization differences.
            normalize = lambda s: re.sub(r"[\s\x00-\x1f]", "", s)
            fixed = []
            for block in a[0].get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    if any(f["location"].get("replace") and pymupdf.Rect(f["location"]["rect"]).intersects(pymupdf.Rect(line["bbox"])) for f in spec["fields"]):
                        continue
                    fixed.append(normalize("".join(s["text"] for s in line["spans"])))
            assert all(line in normalize(text) for line in fixed), "고정 문구가 변경되었습니다"
            assert changed / mask.sum() < 0.005, (spec["file"], "입력란 밖의 시각적 변경", changed)
            b[0].get_pixmap(matrix=pymupdf.Matrix(1.3, 1.3)).save(ROOT / (spec["file"] + "-filled.png"))
            a[0].get_pixmap(matrix=pymupdf.Matrix(1.3, 1.3)).save(ROOT / (spec["file"] + "-original.png"))
        results.append({"key": spec["key"], "name": spec["name"], "source_url": spec["source_url"], "source_page": spec["page"] + 1, "original_sha256": hashlib.sha256(original.read_bytes()).hexdigest(), "input_locations": len(spec["fields"]), "page_count": 1, "changed_pixels_outside_inputs": changed, "fixed_text_preserved": True, "all_values_verified": True})
    (ROOT / "verification.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
