"""Regression coverage for submission geometry and preserved page boundaries."""
import unittest
import base64
from io import BytesIO
from zipfile import ZipFile
from lxml import etree
import pymupdf

from app.professional_templates import BUILTIN_TEMPLATES
from app.routers.templates import SAMPLE_VALUES
from app.services.professional_renderer import render_docx, render_hwpx, item_amounts, HWP_CONTENT_WIDTH
from app.services.renderer import docx_to_pdf_bytes, pdf_preview_pages


class SubmissionLayoutTests(unittest.TestCase):
    def test_editor_preview_preserves_pdf_pages_and_aspect_ratio(self):
        definition = next(t['definition'] for t in BUILTIN_TEMPLATES if t['key'] == 'completion')
        pdf = docx_to_pdf_bytes(render_docx(definition, SAMPLE_VALUES))
        pages = pdf_preview_pages(pdf)
        self.assertEqual(len(pages), 2)
        for page in pages:
            png = pymupdf.Pixmap(base64.b64decode(page['data'].split(',', 1)[1]))
            self.assertEqual((png.width, png.height), (page['width'], page['height']))
            self.assertAlmostEqual(page['width'] / page['height'], 210 / 297, places=3)

    def test_whole_won_rounding_matches_excel(self):
        self.assertEqual(item_amounts({"qty": 1, "unit": 105}), (105, 11))
        self.assertEqual(item_amounts({"qty": 0.5, "unit": 101}), (51, 5))

    def test_hwpx_tables_fit_and_stamp_has_physical_space(self):
        for template in BUILTIN_TEMPLATES:
            with self.subTest(template=template["key"]):
                with ZipFile(BytesIO(render_hwpx(template["definition"], SAMPLE_VALUES))) as z:
                    root = etree.fromstring(z.read("Contents/section0.xml"))
                    ns = {"hp": "http://www.hancom.co.kr/hwpml/2011/paragraph"}
                    for size in root.xpath('//hp:tbl/hp:sz', namespaces=ns):
                        self.assertLessEqual(int(size.get('width')), HWP_CONTENT_WIDTH)
                    if template['key'] == 'seal_registration':
                        self.assertTrue(root.xpath('//hp:cellSz[@height="9100"]', namespaces=ns))

    def test_edited_attachments_and_long_content_survive(self):
        definition = next(t["definition"] for t in BUILTIN_TEMPLATES if t["key"] == "commencement")
        values = dict(SAMPLE_VALUES, attachment_list="실제 첨부자료 1부", work_summary="세부 과업 내용입니다.\n" * 90)
        with pymupdf.open(stream=docx_to_pdf_bytes(render_docx(definition, values)), filetype="pdf") as pdf:
            text = ''.join(p.get_text() for p in pdf)
            self.assertIn('실제 첨부자료', text)
            self.assertNotIn('사용인감계 1부', text)
            self.assertGreater(len(pdf), 1)
        with ZipFile(BytesIO(render_hwpx(definition, values))) as z:
            text = z.read('Preview/PrvText.txt').decode()
            self.assertIn('실제 첨부자료', text)
            self.assertNotIn('사용인감계 1부', text)

    def test_completion_has_separate_detail_page(self):
        definition = next(t["definition"] for t in BUILTIN_TEMPLATES if t["key"] == "completion")
        with pymupdf.open(stream=docx_to_pdf_bytes(render_docx(definition, SAMPLE_VALUES)), filetype="pdf") as pdf:
            self.assertEqual(len(pdf), 2)
            self.assertIn("완 료 내 역 서", pdf[1].get_text())
        with ZipFile(BytesIO(render_hwpx(definition, SAMPLE_VALUES))) as z:
            root = etree.fromstring(z.read("Contents/section0.xml"))
            self.assertTrue(root.xpath('//*[@pageBreak="1"]'))

    def test_all_forms_are_a4_with_content(self):
        for template in BUILTIN_TEMPLATES:
            with self.subTest(template=template["key"]):
                with pymupdf.open(stream=docx_to_pdf_bytes(render_docx(template["definition"], SAMPLE_VALUES)), filetype="pdf") as pdf:
                    for page in pdf:
                        self.assertAlmostEqual(page.rect.width, 595.28, places=1)
                        self.assertAlmostEqual(page.rect.height, 841.89, places=1)
                        self.assertGreater(len(page.get_text()), 30)


if __name__ == "__main__":
    unittest.main()
