"""Security regressions use fictional data and isolated in-memory databases."""
import logging
import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from io import BytesIO

from cryptography.fernet import Fernet, InvalidToken
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.encryption import cipher, encrypt, decrypt, PREFIX
from app.core.security import SESSION_COOKIE, csrf_token, digest, hash_password
from app.models import (AuditLog, AuthSession, AuthThrottle, Company, Contract, Document,
                        SensitiveGrant, StoredFile, Template, User, LibraryAdmin)
from app.professional_templates import BUILTIN_TEMPLATES
from app.routers.templates import SAMPLE_VALUES
from app.services.seal import normalize_seal
from main import app, maintenance
from tests.auth_helpers import PASSWORD, auth_headers, approve

logging.getLogger('httpx2').setLevel(logging.WARNING)


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.users = [User(email=f'security-{i}@example.invalid', name='가상 사용자', password_hash=hash_password(PASSWORD)) for i in (1,2)]
        self.db.add_all(self.users); self.db.flush()
        for user in self.users:
            self.db.add(Company(user_id=user.id, company_name='가상 회사'))
        self.db.commit()
        self.headers = [auth_headers(self.db, user.id) for user in self.users]
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.client.close(); app.dependency_overrides.clear(); self.db.close(); self.engine.dispose()

    def document(self, user=None):
        user = user or self.users[0]
        contract = Contract(user_id=user.id, contract_title='가상 계약', description='기밀 과업 설명')
        template = Template(kind='builtin', name='착수계', definition=next(t['definition'] for t in BUILTIN_TEMPLATES if t['key']=='commencement'))
        self.db.add_all([contract,template]); self.db.flush()
        doc = Document(contract_id=contract.id, template_id=template.id, title='착수계', values=dict(SAMPLE_VALUES))
        self.db.add(doc); self.db.commit()
        return contract, doc

    def test_login_cookie_and_no_legacy_bearer(self):
        response = self.client.post('/api/v1/auth/login', json={'email': self.users[0].email, 'password': PASSWORD})
        self.assertEqual(response.status_code,200)
        self.assertNotIn('access_token',response.json())
        cookie = response.headers['set-cookie'].lower()
        self.assertIn('httponly',cookie); self.assertIn('samesite=strict',cookie)
        token = self.client.cookies[SESSION_COOKIE]
        self.assertIsNotNone(self.db.get(AuthSession,digest(token)))
        self.assertIsNone(self.db.get(AuthSession,token))
        self.client.cookies.clear()
        self.assertEqual(self.client.get('/api/v1/auth/me',headers={'Authorization':'Bearer '+token}).status_code,401)
        with patch.object(settings,'CLOUD_MODE',True):
            secure = self.client.post('/api/v1/auth/login', json={'email':self.users[0].email,'password':PASSWORD})
            self.assertIn('Secure',secure.headers['set-cookie'])

    def test_csrf_and_cross_origin_are_rejected(self):
        cookie = {'Cookie': self.headers[0]['Cookie']}
        self.assertEqual(self.client.put('/api/v1/company',headers=cookie,json={}).status_code,403)
        bad = {**self.headers[0],'X-CSRF-Token':'wrong'}
        self.assertEqual(self.client.put('/api/v1/company',headers=bad,json={}).status_code,403)
        self.assertEqual(self.client.put('/api/v1/company',headers=self.headers[0],json={}).status_code,200)
        for headers in ({**self.headers[0],'Origin':'https://attacker.invalid'}, {**self.headers[0],'Sec-Fetch-Site':'cross-site'}):
            self.assertEqual(self.client.put('/api/v1/company',headers=headers,json={}).status_code,403)
        self.assertEqual(self.client.post('/api/v1/auth/login',headers={'Origin':'https://attacker.invalid'},json={'email':self.users[0].email,'password':PASSWORD}).status_code,403)
        self.assertEqual(self.client.get('/api/v1/auth/csrf',headers=self.headers[0]).headers['Cache-Control'],'no-store')

    def test_logout_and_all_devices_revoke_stolen_cookies(self):
        extra = auth_headers(self.db,self.users[0].id)
        self.assertEqual(self.client.post('/api/v1/auth/logout',headers=self.headers[0]).status_code,200)
        self.assertEqual(self.client.get('/api/v1/auth/me',headers=self.headers[0]).status_code,401)
        self.assertEqual(self.client.get('/api/v1/auth/me',headers=extra).status_code,200)
        self.assertEqual(self.client.post('/api/v1/auth/logout-all',headers=extra).status_code,200)
        self.assertEqual(self.client.get('/api/v1/auth/me',headers=extra).status_code,401)
        self.assertEqual(self.client.get('/api/v1/auth/me',headers=self.headers[1]).status_code,200)

    def test_expired_session_is_rejected(self):
        self.db.execute(text('UPDATE auth_sessions SET expires_at=:expired'),{'expired':datetime.utcnow()-timedelta(seconds=1)})
        self.db.commit(); self.db.expire_all()
        self.assertEqual(self.client.get('/api/v1/auth/me',headers=self.headers[0]).status_code,401)

    def test_login_is_rate_limited_across_clients(self):
        for _ in range(10):
            res=self.client.post('/api/v1/auth/login',json={'email':self.users[0].email,'password':'incorrect'})
            self.assertEqual(res.status_code,401)
        res=self.client.post('/api/v1/auth/login',json={'email':self.users[0].email,'password':PASSWORD})
        self.assertEqual(res.status_code,429); self.assertIn('Retry-After',res.headers)
        self.assertEqual(self.db.scalar(select(AuthThrottle.attempts).where(AuthThrottle.attempts==11)),11)

    def test_seal_read_grants_are_scoped_session_bound_and_single_use(self):
        company=self.users[0].company
        company.seal_image='data:image/png;base64,fictional-secret'; self.db.commit()
        res=self.client.get('/api/v1/company',headers=self.headers[0])
        self.assertTrue(res.json()['has_seal']);self.assertEqual(res.json()['seal_image'],'')
        self.assertEqual(self.client.get('/api/v1/company/seal',headers=self.headers[0]).status_code,403)
        grant=approve(self.client,self.headers[0],'seal:read')
        second=auth_headers(self.db,self.users[0].id)
        self.assertEqual(self.client.get('/api/v1/company/seal',headers={**second,'X-Sensitive-Grant':grant['X-Sensitive-Grant']}).status_code,403)
        self.assertEqual(self.client.delete('/api/v1/company/seal',headers=grant).status_code,403)
        self.assertEqual(self.client.get('/api/v1/company/seal',headers=grant).json()['seal_image'],company.seal_image)
        self.assertEqual(self.client.get('/api/v1/company/seal',headers=grant).status_code,403)
        self.assertEqual(self.client.get('/api/v1/company',headers=self.headers[1]).json()['seal_image'],'')

    def test_expired_grant_cannot_be_used(self):
        grant=approve(self.client,self.headers[0],'seal:read')
        self.db.query(SensitiveGrant).update({'expires_at':datetime.utcnow()-timedelta(seconds=1)});self.db.commit()
        self.assertEqual(self.client.get('/api/v1/company/seal',headers=grant).status_code,403)

    def test_all_seal_output_routes_require_grants_and_preview_is_unstamped(self):
        import pymupdf
        c,d=self.document()
        image=BytesIO();Image.new('RGBA',(60,60),(180,0,0,100)).save(image,format='PNG')
        self.users[0].company.seal_image=normalize_seal(image.getvalue());self.db.commit()
        preview=self.client.get(f'/api/v1/documents/{d.id}/preview-pages',headers=self.headers[0])
        self.assertEqual(preview.status_code,200)
        # Preview HTML must not expose the stamp, and GET output cannot bypass approval.
        from app.services.documents import build_pdf
        with pymupdf.open(stream=build_pdf(d),filetype='pdf') as pdf:
            self.assertFalse(any(p.get_images() for p in pdf))
        for fmt in ('pdf','native','docx'):
            self.assertEqual(self.client.get(f'/api/v1/documents/{d.id}/download?format={fmt}',headers=self.headers[0]).status_code,403)
        for path in (f'/api/v1/contracts/{c.id}/export',):
            self.assertEqual(self.client.get(path,headers=self.headers[0]).status_code,403)
        self.assertEqual(self.client.post(f'/api/v1/contracts/{c.id}/mail',headers=self.headers[0],json={'to':'fictional@example.invalid','document_ids':[d.id]}).status_code,403)
        grant=approve(self.client,self.headers[0],f'document:{d.id}:download')
        out=self.client.get(f'/api/v1/documents/{d.id}/download?format=pdf',headers=grant)
        self.assertEqual(out.status_code,200)
        with pymupdf.open(stream=out.content,filetype='pdf') as pdf:
            self.assertTrue(any(p.get_images() for p in pdf))
        self.assertEqual(self.client.get(f'/api/v1/documents/{d.id}/download?format=pdf',headers=grant).status_code,403)

    def test_other_accounts_cannot_access_any_document_or_contract_route(self):
        c,d=self.document();h=self.headers[1]
        for suffix in ('','/preview','/preview-pages','/download?format=pdf','/download?format=native','/download?format=docx'):
            self.assertEqual(self.client.get(f'/api/v1/documents/{d.id}{suffix}',headers=h).status_code,404,suffix)
        for method,path,body in [('PUT',f'/documents/{d.id}',{'values':{}}),('DELETE',f'/documents/{d.id}',None),('POST',f'/documents/{d.id}/reapply',None),('POST',f'/documents/{d.id}/generate/work_summary',None),('GET',f'/contracts/{c.id}',None),('GET',f'/contracts/{c.id}/documents',None),('GET',f'/contracts/{c.id}/export',None),('POST',f'/contracts/{c.id}/validate',None),('POST',f'/contracts/{c.id}/mail',{'to':'fictional@example.invalid','document_ids':[d.id]}),('DELETE',f'/contracts/{c.id}',None)]:
            self.assertEqual(self.client.request(method,'/api/v1'+path,headers=h,json=body).status_code,404,path)
        self.assertEqual(self.client.post('/api/v1/auth/reauthenticate',headers=h,json={'password':PASSWORD,'scope':f'document:{d.id}:download'}).status_code,404)

    def test_private_templates_stay_private_even_to_library_admin(self):
        t=Template(owner_id=self.users[0].id,kind='uploaded',name='비공개',source_type='docx',fields=[],definition={})
        self.db.add(t);self.db.commit()
        self.db.add(LibraryAdmin(user_id=self.users[1].id));self.db.commit()
        h=self.headers[1]
        with patch.object(settings,'LIBRARY_ADMIN_EMAILS',{self.users[1].email}):
            for suffix in ('','/original','/sample-file','/review-preview','/review-preview-pages'):
                self.assertEqual(self.client.get(f'/api/v1/templates/{t.id}{suffix}',headers=h).status_code,404,suffix)
            for suffix,body in (('/name',{'name':'changed'}),('/favorite',{'favorite':True}),('/mapping',{'fields':[]})):
                self.assertEqual(self.client.put(f'/api/v1/templates/{t.id}{suffix}',headers=h,json=body).status_code,404,suffix)

    def test_registering_allowlisted_email_does_not_grant_admin(self):
        from app.services.library import is_admin
        with patch.object(settings,'LIBRARY_ADMIN_EMAILS',{self.users[0].email}):
            self.assertFalse(is_admin(self.users[0]))
            self.assertFalse(self.client.get('/api/v1/templates/library-settings',headers=self.headers[0]).json()['is_admin'])

    def test_ownerless_private_template_is_not_treated_as_public(self):
        t=Template(owner_id=None,kind='uploaded',name='잘못된 비공개 상태',status='ready',definition={'library':{'scope':'private'}})
        self.db.add(t);self.db.commit()
        self.assertEqual(self.client.get(f'/api/v1/templates/{t.id}',headers=self.headers[0]).status_code,404)
        self.assertNotIn(t.id,[row['id'] for row in self.client.get('/api/v1/templates',headers=self.headers[0]).json()])

    def test_encrypted_database_values_are_not_plaintext(self):
        c,d=self.document()
        self.users[0].company.seal_image='confidential-seal'; self.db.add(StoredFile(key='x.docx',owner_id=self.users[0].id,data=b'confidential-file'))
        self.db.commit()
        raw=self.db.execute(text('SELECT "values" FROM documents')).scalar()
        self.assertNotIn(SAMPLE_VALUES['company_name'],str(raw))
        self.assertNotIn('confidential-seal',self.db.execute(text('SELECT seal_image FROM companies WHERE user_id=:uid'),{'uid':self.users[0].id}).scalar())
        self.assertNotIn(b'confidential-file',bytes(self.db.execute(text('SELECT data FROM stored_files')).scalar()))
        self.db.expire_all();self.assertEqual(self.db.get(Document,d.id).values['company_name'],SAMPLE_VALUES['company_name'])
        encrypted=encrypt(b'confidential');self.assertTrue(encrypted.startswith(PREFIX))
        tampered=encrypted[:-4]+b'aaaa'
        with self.assertRaises(InvalidToken):decrypt(tampered)

    def test_delete_data_is_reauthenticated_and_leaves_other_accounts(self):
        self.document();other,_=self.document(self.users[1])
        self.assertEqual(self.client.delete('/api/v1/privacy/data',headers=self.headers[0]).status_code,403)
        result=self.client.delete('/api/v1/privacy/data',headers=approve(self.client,self.headers[0],'data:delete'))
        self.assertEqual(result.status_code,200)
        self.assertIsNotNone(self.db.get(Contract,other.id))
        self.assertEqual(self.db.query(Contract).filter_by(user_id=self.users[0].id).count(),0)
        self.assertEqual(self.db.query(Company).filter_by(user_id=self.users[0].id).count(),0)
        self.assertEqual(self.client.get('/api/v1/auth/me',headers=self.headers[0]).status_code,200)

    def test_maintenance_endpoint_fails_closed(self):
        with patch.dict(os.environ,{'CRON_SECRET':''}):
            self.assertEqual(self.client.get('/api/v1/internal/maintenance').status_code,401)
        with patch.dict(os.environ,{'CRON_SECRET':'a'*40}):
            self.assertEqual(self.client.get('/api/v1/internal/maintenance',headers={'Authorization':'Bearer wrong'}).status_code,401)
            self.assertEqual(self.client.get('/api/v1/internal/maintenance',headers={'Authorization':'Bearer '+'a'*40}).status_code,200)

    def test_legacy_data_migration_is_repeatable_and_preserves_values(self):
        from scripts.migrate_security import migrate_data
        c,d=self.document()
        # A pre-upgrade plaintext database value must be readable, then rewritten encrypted.
        self.db.execute(text('UPDATE companies SET account_number=:value WHERE user_id=:uid'),{'value':'fictional-bank-number','uid':self.users[0].id})
        self.db.commit(); self.db.expire_all()
        self.assertEqual(self.users[0].company.account_number,'fictional-bank-number')
        for _ in range(2):
            migrate_data(self.db); self.db.commit(); self.db.expire_all()
            self.assertEqual(self.db.get(Document,d.id).values['company_name'],SAMPLE_VALUES['company_name'])
            self.assertEqual(self.users[0].company.account_number,'fictional-bank-number')
            raw=self.db.execute(text('SELECT account_number FROM companies WHERE user_id=:uid'),{'uid':self.users[0].id}).scalar()
            self.assertTrue(raw.startswith(PREFIX.decode()))


if __name__ == '__main__':unittest.main()
