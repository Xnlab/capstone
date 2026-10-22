import unittest
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile

from fastapi.testclient import TestClient
from lxml import etree
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import create_access_token
from app.core.config import settings
from app.models import User
from app.professional_templates import BUILTIN_TEMPLATES
from app.services.professional_renderer import render_hwpx
from app.services import hwpx_forms
from main import app


def fixture():
    definition = next(t['definition'] for t in BUILTIN_TEMPLATES if t['key'] == 'commencement')
    data = render_hwpx(definition, {'company_name': '{{company_name}}', 'representative': '{{representative}}'})
    source, output = ZipFile(BytesIO(data)), BytesIO()
    with ZipFile(output, 'w') as archive:
        for entry in source.infolist():
            archive.writestr(entry, source.read(entry))
        archive.writestr('BinData/preserved.png', b'preserved-original-image')
    source.close()
    return output.getvalue()


class HwpxUploadTests(unittest.TestCase):
    def test_fill_preserves_package_styles_images_fixed_text_and_source(self):
        source = fixture()
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'form.hwpx'
            path.write_bytes(source)
            analysis = hwpx_forms.analyze(path)
            fields = []
            for item in analysis['items']:
                if item['label'].replace(' ', '') == '계약명':
                    fields.append({**item, 'field_key': 'contract_title'})
                elif item['label'] == '회사명':
                    fields.append({**item, 'field_key': 'company_name'})
            self.assertEqual(len(fields), 2)
            filled = hwpx_forms.fill(path, fields, {'contract_title': '실제 계약 제목', 'company_name': '시험 회사'})
            self.assertEqual(path.read_bytes(), source)
            with ZipFile(BytesIO(source)) as before, ZipFile(BytesIO(filled)) as after:
                self.assertEqual(before.read('Contents/header.xml'), after.read('Contents/header.xml'))
                self.assertEqual(before.read('BinData/preserved.png'), after.read('BinData/preserved.png'))
                root = etree.fromstring(after.read('Contents/section0.xml'))
                text = ''.join(root.itertext())
                self.assertIn('실제 계약 제목', text)
                self.assertIn('시험 회사', text)
                self.assertIn('착수계를 제출합니다', text)
                self.assertEqual(len(root.findall('.//hp:tbl', hwpx_forms.NS)), 2)
                self.assertIn('{{representative}}', text)

    def test_placeholder_split_across_styled_runs_and_bad_location(self):
        source = fixture()
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'form.hwpx'
            entries, files = hwpx_forms._read(source)
            root = hwpx_forms._roots(files)['Contents/section0.xml']
            paragraph = root.findall('hp:p', hwpx_forms.NS)[1]
            for node in list(paragraph):
                paragraph.remove(node)
            for text, style in [('고정 {{contract_', '15'), ('title}} 끝', '16')]:
                run = etree.SubElement(paragraph, '{' + hwpx_forms.HP + '}run', charPrIDRef=style)
                etree.SubElement(run, '{' + hwpx_forms.HP + '}t').text = text
            files['Contents/section0.xml'] = etree.tostring(root)
            with ZipFile(path, 'w') as archive:
                for entry in entries:
                    archive.writestr(entry, files[entry.filename])
            item = next(i for i in hwpx_forms.analyze(path)['items'] if i['label'] == '계약명' and i['location']['type'] == 'hwpx_placeholder')
            result = hwpx_forms.fill(path, [{**item, 'field_key': 'contract_title'}], {'contract_title': '시험'})
            with ZipFile(BytesIO(result)) as archive:
                root = etree.fromstring(archive.read('Contents/section0.xml'))
                text = ''.join(root.itertext())
                self.assertIn('고정 시험 끝', text)
                self.assertTrue(root.xpath('//*[@charPrIDRef="15"]'))
            with self.assertRaises(ValueError):
                hwpx_forms.fill(path, [{'field_key': 'contract_title', 'location': {'type': 'hwpx_cell', 'section': '../../outside.xml', 'index': 0}}], {'contract_title': '시험'})

    def test_upload_mapping_autofill_native_and_hwp_sidecar_cleanup(self):
        engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            user = User(email='hwpx@example.test', password_hash='test-only')
            db.add(user); db.commit(); uid = user.id

        def session():
            with Session(engine) as db:
                yield db

        app.dependency_overrides[get_db] = session
        try:
            with TemporaryDirectory() as folder, patch.object(settings, 'UPLOAD_DIR', Path(folder)), patch.object(settings, 'OPENAI_API_KEY', ''):
                client = TestClient(app)
                headers = {'Authorization': 'Bearer ' + create_access_token(uid)}
                payload = fixture()
                response = client.post('/api/v1/templates/upload', headers=headers, files={'file': ('양식.hwpx', payload, 'application/hwp+zip')})
                self.assertEqual(response.status_code, 200, response.text)
                template = response.json()['template']
                self.assertEqual(template['source_type'], 'hwpx')
                self.assertEqual(template['output_format'], 'hwpx')
                self.assertGreater(len(template['fields']), 2)
                saved = client.put(f"/api/v1/templates/{template['id']}/mapping", headers=headers, json={'fields': template['fields']})
                self.assertEqual(saved.status_code, 200, saved.text)
                company = client.put('/api/v1/company', headers=headers, json={'company_name': '시험 회사'})
                self.assertEqual(company.status_code, 200)
                contract = client.post('/api/v1/contracts', headers=headers, json={'contract_title': '업로드 양식 시험', 'contract_date': '2026-10-22'}).json()
                created = client.post(f"/api/v1/contracts/{contract['id']}/documents", headers=headers, json={'template_id': template['id']})
                self.assertEqual(created.status_code, 200, created.text)
                doc = created.json()
                self.assertEqual(doc['output_format'], 'hwpx')
                native = client.get(f"/api/v1/documents/{doc['id']}/download?format=native", headers=headers)
                self.assertEqual(native.status_code, 200, native.text[:100])
                with ZipFile(BytesIO(native.content)) as archive:
                    self.assertIn('업로드 양식 시험', archive.read('Contents/section0.xml').decode())
                original = client.get(f"/api/v1/templates/{template['id']}/original", headers=headers)
                self.assertEqual(original.content, payload)
                sample = client.get(f"/api/v1/templates/{template['id']}/sample-file", headers=headers)
                self.assertTrue(sample.headers['content-type'].startswith('application/hwp+zip'))
                def convert(_source, destination, _format):
                    destination.write_bytes(payload)
                with patch('app.services.hancom.convert', side_effect=convert) as converter:
                    hwp = client.post('/api/v1/templates/upload', headers=headers, files={'file': ('old.hwp', bytes.fromhex('D0CF11E0A1B11AE1') + b'fixture', 'application/x-hwp')})
                    self.assertEqual(hwp.status_code, 200, hwp.text)
                    self.assertTrue(converter.called)
                tid = hwp.json()['template']['id']
                sidecars = list(Path(folder).rglob('*.hwp'))
                self.assertEqual(len(sidecars), 1)
                normalized = sidecars[0].with_suffix('.hwpx')
                self.assertTrue(normalized.is_file())
                self.assertEqual(client.delete(f'/api/v1/templates/{tid}', headers=headers).status_code, 200)
                self.assertFalse(normalized.exists())
                self.assertFalse(sidecars[0].exists())
                # Losing the original must never silently substitute a different form.
                list(Path(folder).rglob('*.hwpx'))[0].unlink()
                self.assertEqual(client.get(f"/api/v1/documents/{doc['id']}/download?format=native", headers=headers).status_code, 410)
        finally:
            app.dependency_overrides.pop(get_db, None)
            engine.dispose()
