"""Seal ownership, image validation and native/PDF embedding regression tests."""
import base64
import unittest
from io import BytesIO
from zipfile import ZipFile

import pymupdf
from PIL import Image, ImageDraw
from lxml import etree
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import hash_password
from tests.auth_helpers import PASSWORD, auth_headers, approve
from app.models import User, Company, Contract, Template, Document
from app.professional_templates import BUILTIN_TEMPLATES
from app.routers.templates import SAMPLE_VALUES
from app.services.professional_renderer import render_docx, render_hwpx, render_quotation_xlsx
from app.services.renderer import docx_to_pdf_bytes
from app.services.seal import normalize_seal, company_seal
from main import app


def sample_seal():
    image = Image.new('RGBA', (240, 240))
    draw = ImageDraw.Draw(image)
    draw.ellipse((5, 5, 235, 235), outline='#c51f30', width=10)
    draw.line((60, 65, 180, 175), fill='#c51f30', width=9)
    draw.line((180, 65, 60, 175), fill='#c51f30', width=9)
    result = BytesIO()
    image.save(result, format='PNG')
    return result.getvalue()


class CompanySealTests(unittest.TestCase):
    def test_owner_only_upload_resize_remove_and_document_rendering(self):
        engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            users = [User(email=f'seal-{i}@example.com', password_hash=hash_password(PASSWORD)) for i in (1, 2)]
            db.add_all(users)
            db.flush()
            ids = [user.id for user in users]
            contract = Contract(user_id=ids[0], contract_title='날인 시험')
            template = Template(kind='builtin', name='완료계', definition=next(t['definition'] for t in BUILTIN_TEMPLATES if t['key'] == 'completion'))
            db.add_all([contract, template])
            db.flush()
            doc = Document(contract_id=contract.id, template_id=template.id, title='완료계', values=SAMPLE_VALUES)
            db.add(doc); db.commit()
            doc_id = doc.id

        def session():
            with Session(engine) as db:
                yield db

        app.dependency_overrides[get_db] = session
        try:
            client = TestClient(app)
            with Session(engine) as db:
                headers = [auth_headers(db, i) for i in ids]
            self.assertEqual(client.post('/api/v1/company/seal', files={'file': ('seal.png', sample_seal(), 'image/png')}).status_code, 401)
            bad = client.post('/api/v1/company/seal', headers=approve(client, headers[0], 'seal:manage'), files={'file': ('seal.png', b'<svg/>', 'image/png')})
            self.assertEqual(bad.status_code, 400)
            oversized = client.post('/api/v1/company/seal', headers=approve(client, headers[0], 'seal:manage'), files={'file': ('seal.png', b'x' * (3 * 1024 * 1024 + 1), 'image/png')})
            self.assertEqual(oversized.status_code, 400)
            response = client.post('/api/v1/company/seal', headers=approve(client, headers[0], 'seal:manage'), files={'file': ('seal.png', sample_seal(), 'image/png')})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertTrue(response.json()['has_seal'])
            self.assertEqual(response.json()['seal_image'], '')
            other = client.get('/api/v1/company', headers=headers[1])
            self.assertEqual(other.json()['seal_image'], '')
            self.assertEqual(client.get(f'/api/v1/documents/{doc_id}/preview-pages', headers=headers[1]).status_code, 404)
            self.assertEqual(client.put('/api/v1/company/seal', headers=approve(client, headers[0], 'seal:manage'), json={'size_mm': 100}).status_code, 422)
            resized = client.put('/api/v1/company/seal', headers=approve(client, headers[0], 'seal:manage'), json={'size_mm': 25})
            self.assertEqual(resized.json()['seal_size_mm'], 25)
            pdf = client.get(f'/api/v1/documents/{doc_id}/download?format=pdf', headers=approve(client, headers[0], f'document:{doc_id}:download'))
            self.assertEqual(pdf.status_code, 200, pdf.text[:200])
            with pymupdf.open(stream=pdf.content, filetype='pdf') as output:
                self.assertEqual(len(output), 2)
                for page in output:
                    self.assertTrue(page.get_images())
                    self.assertIn('(인)', page.get_text())
            removed = client.delete('/api/v1/company/seal', headers=approve(client, headers[0], 'seal:manage'))
            self.assertEqual(removed.json()['seal_image'], '')
            pdf = client.get(f'/api/v1/documents/{doc_id}/download?format=pdf', headers=headers[0])
            with pymupdf.open(stream=pdf.content, filetype='pdf') as output:
                self.assertFalse(output[0].get_images())
        finally:
            app.dependency_overrides.pop(get_db, None)
            engine.dispose()

    def test_native_embedded_image_and_behind_text_anchor(self):
        seal = company_seal(Company(seal_image=normalize_seal(sample_seal()), seal_size_mm=20))
        for template in BUILTIN_TEMPLATES:
            definition = template['definition']
            if template['key'] == 'quotation':
                with ZipFile(BytesIO(render_quotation_xlsx(SAMPLE_VALUES, seal))) as archive:
                    self.assertIn('xl/media/image1.png', archive.namelist())
            else:
                with ZipFile(BytesIO(render_hwpx(definition, SAMPLE_VALUES, seal))) as archive:
                    self.assertEqual(archive.read('BinData/companySeal.png'), seal['data'])
                    root = etree.fromstring(archive.read('Contents/section0.xml'))
                    pics = root.xpath('//*[local-name()="pic"]')
                    self.assertEqual(len(pics), 2 if template['key'] == 'completion' else 1)
                    self.assertTrue(all(pic.get('textWrap') == 'BEHIND_TEXT' for pic in pics))
                    self.assertIn(b'companySeal', archive.read('Contents/content.hpf'))
            docx = render_docx(definition, SAMPLE_VALUES, seal)
            anchors = docx.element.xpath('//wp:anchor')
            self.assertTrue(anchors)
            self.assertTrue(all(anchor.get('behindDoc') == '1' for anchor in anchors))
            # Verify every template's preview still renders, including the quote's signature cell.
            with pymupdf.open(stream=docx_to_pdf_bytes(docx), filetype='pdf') as output:
                self.assertTrue(any(page.get_images() for page in output))
                if template['key'] == 'commencement':
                    page = output[0]
                    textpage = page.get_textpage()
                    name = page.search_for('김대표', textpage=textpage)[0]
                    image = page.get_image_rects(page.get_images()[0][0])[0]
                    marker = page.search_for('(인)', textpage=textpage)[0]
                    self.assertGreater(image.x0, name.x1)
                    self.assertTrue(image.contains(marker))

    def test_non_square_image_retains_proportions(self):
        image = Image.new('RGB', (400, 200), 'red')
        data = BytesIO(); image.save(data, format='JPEG')
        seal = company_seal(Company(seal_image=normalize_seal(data.getvalue()), seal_size_mm=20))
        self.assertEqual((seal['width_mm'], seal['height_mm']), (20, 10))


if __name__ == '__main__':
    unittest.main()
