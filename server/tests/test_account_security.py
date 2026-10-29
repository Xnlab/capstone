"""Fictional accounts; isolated database/key. Never enrolls a real user."""
import base64
import logging
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet, InvalidToken
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.encryption import cipher, key_status, encrypt, decrypt
from app.core.mfa import totp
from app.core.security import SESSION_COOKIE, digest, hash_password, verify_password
from app.models import AuthSession, AuthThrottle, Company, MfaChallenge, MfaCredential, MfaRecovery, Template, User
from main import app, maintenance
from scripts.manage_keys import verify_primary
from scripts.migrate_security import migrate_data
from tests.auth_helpers import auth_headers, PASSWORD

logging.getLogger('httpx2').setLevel(logging.WARNING)


class AccountSecurityTests(unittest.TestCase):
    def setUp(self):
        self.keys = patch.dict(os.environ, {'DATA_ENCRYPTION_KEYS': Fernet.generate_key().decode(), 'DATA_ENCRYPTION_KEY_FILE': ''})
        self.keys.start(); cipher.cache_clear()
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user = User(email='fictional@example.invalid', password_hash=hash_password(PASSWORD))
        self.db.add(self.user); self.db.flush()
        self.db.add(Company(user_id=self.user.id, company_name='가상 회사'))
        self.db.commit()
        self.h = auth_headers(self.db, self.user.id)
        def db_override():
            try:
                yield self.db
            finally:
                self.db.rollback()
        app.dependency_overrides[get_db] = db_override
        self.client = TestClient(app)
        self.clock = 1800000000
        self.time_patch = patch('app.core.mfa.time.time', side_effect=lambda: self.clock)
        self.time_patch.start()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.time_patch.stop(); self.client.close(); app.dependency_overrides.clear()
        self.db.close(); self.engine.dispose(); self.keys.stop(); cipher.cache_clear()

    def post(self, path, body, headers=None):
        return self.client.post('/api/v1/auth/' + path, json=body, headers=self.h if headers is None else headers)

    def adopt(self, res):
        self.assertEqual(res.status_code, 200, res.text)
        token = res.cookies.get(SESSION_COOKIE)
        self.h = {'Cookie': f'{SESSION_COOKIE}={token}', 'X-CSRF-Token': res.json()['csrf_token']}

    def enable(self):
        res = self.post('mfa/setup', {'password': PASSWORD})
        self.assertEqual(res.status_code, 200, res.text)
        self.secret = res.json()['secret']
        res = self.post('mfa/enable', {'password': PASSWORD, 'code': self.code()})
        self.adopt(res)
        self.codes = res.json()['recovery_codes']

    def code(self, advance=False):
        if advance: self.clock += 30
        return totp(self.secret, self.clock // 30)

    def challenge(self):
        self.client.cookies.clear()
        res = self.post('login', {'email': self.user.email, 'password': PASSWORD}, headers={})
        self.assertEqual(res.status_code, 200, res.text)
        self.assertTrue(res.json()['mfa_required'])
        self.assertNotIn('set-cookie', res.headers)
        return res.json()['challenge']

    def test_rfc6238_vectors(self):
        secret = base64.b32encode(b'12345678901234567890').decode()
        for seconds, expected in [(59,'94287082'), (1111111109,'07081804'), (1111111111,'14050471'), (1234567890,'89005924'), (2000000000,'69279037'), (20000000000,'65353130')]:
            self.assertEqual(totp(secret, seconds // 30, digits=8), expected)

    def test_setup_needs_password_csrf_and_current_session(self):
        self.assertEqual(self.post('mfa/setup', {'password':'wrong'}).status_code, 403)
        self.assertEqual(self.post('mfa/setup', {'password':PASSWORD}, headers={'Cookie':self.h['Cookie']}).status_code, 403)
        self.assertEqual(self.post('mfa/setup', {'password':PASSWORD}).status_code, 200)
        credential = self.db.get(MfaCredential, self.user.id)
        secret = credential.secret
        raw = self.db.scalar(text('SELECT secret FROM mfa_credentials'))
        self.assertNotIn(secret, raw)
        other = auth_headers(self.db, self.user.id)
        self.assertEqual(self.post('mfa/enable', {'password':PASSWORD, 'code':totp(secret,self.clock//30)}, headers=other).status_code, 409)
        credential.pending_expires = datetime.utcnow() - timedelta(seconds=1); self.db.commit()
        self.assertEqual(self.post('mfa/enable', {'password':PASSWORD, 'code':totp(secret,self.clock//30)}).status_code, 409)

    def test_enable_revokes_sessions_and_does_not_expose_stored_secrets(self):
        old = self.h.copy()
        self.enable()
        self.assertEqual(len(self.codes),8)
        self.assertEqual(self.client.get('/api/v1/auth/me',headers=old).status_code,401)
        status = self.client.get('/api/v1/auth/mfa',headers=self.h).json()
        self.assertEqual(status, {'enabled':True,'recovery_remaining':8})
        raw = str(self.db.execute(text('SELECT * FROM mfa_recovery')).all())
        for code in self.codes: self.assertNotIn(code.replace('-',''), raw)
        self.assertEqual(self.post('mfa/setup',{'password':PASSWORD}).status_code,409)

    def test_login_has_no_session_before_factor_and_blocks_replay(self):
        self.enable()
        challenge = self.challenge()
        self.assertEqual(self.client.get('/api/v1/auth/me').status_code,401)
        self.assertEqual(self.post('mfa/verify',{'challenge':challenge,'code':self.code()},headers={}).status_code,403)
        code = self.code(True)
        res = self.post('mfa/verify',{'challenge':challenge,'code':code},headers={})
        self.adopt(res)
        self.assertEqual(self.post('mfa/verify',{'challenge':challenge,'code':self.code(True)},headers={}).status_code,403)
        another = self.challenge()
        self.assertEqual(self.post('mfa/verify',{'challenge':another,'code':code},headers={}).status_code,403)

    def test_expired_cross_origin_and_rate_limited_challenge(self):
        self.enable(); challenge = self.challenge()
        self.assertEqual(self.post('mfa/verify', {'challenge':challenge,'code':self.code(True)}, headers={'Origin':'https://evil.invalid'}).status_code,403)
        for _ in range(10):
            self.assertEqual(self.post('mfa/verify', {'challenge':challenge,'code':'invalid'}, headers={}).status_code,403)
        self.assertEqual(self.post('mfa/verify', {'challenge':challenge,'code':'invalid'}, headers={}).status_code,429)
        self.db.execute(text('DELETE FROM auth_throttles')); self.db.commit()
        row = self.db.get(MfaChallenge,digest(challenge)); row.expires_at=datetime.utcnow()-timedelta(seconds=1); self.db.commit()
        self.assertEqual(self.post('mfa/verify', {'challenge':challenge,'code':self.code(True)}, headers={}).status_code,403)

    def test_recovery_code_once_and_recovery_login_revokes_other_sessions(self):
        self.enable(); old = self.h.copy(); challenge = self.challenge()
        res = self.post('mfa/verify', {'challenge':challenge,'code':self.codes[0]}, headers={})
        self.adopt(res)
        self.assertEqual(self.client.get('/api/v1/auth/me',headers=old).status_code,401)
        self.assertEqual(self.client.get('/api/v1/auth/mfa',headers=self.h).json()['recovery_remaining'],7)
        challenge = self.challenge()
        self.assertEqual(self.post('mfa/verify', {'challenge':challenge,'code':self.codes[0]}, headers={}).status_code,403)

    def test_sensitive_grants_require_second_factor_and_are_single_use(self):
        self.enable()
        self.assertEqual(self.post('reauthenticate',{'password':PASSWORD,'scope':'seal:read'}).status_code,403)
        res=self.post('reauthenticate',{'password':PASSWORD,'scope':'seal:read','code':self.code(True)})
        self.assertEqual(res.status_code,200,res.text)
        self.assertEqual(self.post('reauthenticate',{'password':PASSWORD,'scope':'seal:read','code':self.code()}).status_code,403)

    def test_disable_requires_existing_factor_and_revokes_all_old_sessions(self):
        self.enable(); old=self.h.copy()
        self.assertEqual(self.post('mfa/disable',{'password':PASSWORD}).status_code,403)
        self.adopt(self.post('mfa/disable',{'password':PASSWORD,'code':self.code(True)}))
        self.assertEqual(self.client.get('/api/v1/auth/me',headers=old).status_code,401)
        self.assertFalse(self.client.get('/api/v1/auth/mfa',headers=self.h).json()['enabled'])
        self.assertEqual(self.db.scalar(select(MfaRecovery.code_hash).limit(1)),None)

    def test_password_change_and_recovery_regeneration_revoke_pending_logins(self):
        self.enable(); challenge=self.challenge(); old=self.h.copy()
        res=self.post('mfa/recovery',{'password':PASSWORD,'code':self.code(True)})
        self.adopt(res)
        self.assertNotEqual(self.codes,res.json()['recovery_codes'])
        self.assertIsNone(self.db.get(MfaChallenge,digest(challenge)))
        new='new-fictional-password-2026'
        self.assertEqual(self.post('password',{'password':PASSWORD,'new_password':new}).status_code,403)
        self.adopt(self.post('password',{'password':PASSWORD,'new_password':new,'code':self.code(True)}))
        self.db.refresh(self.user)
        self.assertTrue(verify_password(new,self.user.password_hash))
        self.assertEqual(self.client.get('/api/v1/auth/me',headers=old).status_code,401)
        self.assertEqual(self.post('login',{'email':self.user.email,'password':PASSWORD},headers={}).status_code,401)

    def test_expired_pending_secrets_are_removed_by_maintenance(self):
        self.post('mfa/setup',{'password':PASSWORD})
        credential=self.db.get(MfaCredential,self.user.id)
        credential.pending_expires=datetime.utcnow()-timedelta(seconds=1); self.db.commit()
        maintenance(self.db)
        self.assertIsNone(self.db.get(MfaCredential,self.user.id))


class KeyManagementTests(unittest.TestCase):
    def setUp(self):
        self.old=Fernet.generate_key(); self.new=Fernet.generate_key()
        self.env=patch.dict(os.environ,{'DATA_ENCRYPTION_KEYS':self.old.decode(),'DATA_ENCRYPTION_KEY_FILE':''})
        self.env.start(); cipher.cache_clear()
        self.addCleanup(self.env.stop); self.addCleanup(cipher.cache_clear)

    def test_external_file_source_and_safe_status_and_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'keys'; path.write_bytes(self.old); path.chmod(0o600)
            os.environ['DATA_ENCRYPTION_KEY_FILE']=str(path)
            with self.assertRaises(RuntimeError): cipher()
            os.environ['DATA_ENCRYPTION_KEYS']=''; cipher.cache_clear()
            self.assertEqual(decrypt(encrypt(b'fictional')),b'fictional')
            status=key_status()
            self.assertEqual(status['source'],'mounted_file')
            self.assertNotIn(self.old.decode(),str(status))
            path.write_text('not-a-key'); cipher.cache_clear()
            with self.assertRaises(RuntimeError): cipher()
            path.unlink(); cipher.cache_clear()
            with self.assertRaises(RuntimeError): cipher()

    def test_rotation_includes_rows_mfa_and_local_originals_and_can_retire_old_key(self):
        engine=create_engine('sqlite://'); Base.metadata.create_all(engine)
        with Session(engine) as db, tempfile.TemporaryDirectory() as tmp, patch.object(settings,'CLOUD_MODE',False), patch.object(settings,'UPLOAD_DIR',Path(tmp)):
            user=User(email='key-test@example.invalid',password_hash='unused'); db.add(user); db.flush()
            db.add(Company(user_id=user.id,company_name='가상 암호화 회사'))
            original=Path(tmp)/'fictional.hwpx'; original.write_bytes(encrypt(b'fictional original'))
            db.add(Template(owner_id=user.id,kind='uploaded',name='가상 양식',source_path=str(original),source_type='hwpx',definition={'fictional':True},fields=[]))
            db.add(MfaCredential(user_id=user.id,secret='TESTSECRET',enabled=1,last_step=1,pending_session='test',pending_expires=datetime.utcnow()))
            db.commit()
            os.environ['DATA_ENCRYPTION_KEYS']=','.join([self.new.decode(),self.old.decode()]); cipher.cache_clear()
            with self.assertRaises(InvalidToken): verify_primary(db)
            migrate_data(db,rotate_files=True); db.commit()
            result=verify_primary(db); self.assertEqual(result['verified_originals'],1)
            os.environ['DATA_ENCRYPTION_KEYS']=self.new.decode(); cipher.cache_clear(); db.expire_all()
            self.assertEqual(db.scalar(select(Company.company_name)),'가상 암호화 회사')
            self.assertEqual(db.get(MfaCredential,user.id).secret,'TESTSECRET')
            self.assertEqual(decrypt(original.read_bytes()),b'fictional original')
            self.assertGreater(verify_primary(db)['verified_encrypted_values'],0)
        engine.dispose()

    def test_duplicate_keys_rejected_without_printing_secrets(self):
        os.environ['DATA_ENCRYPTION_KEYS']=self.old.decode()+','+self.old.decode(); cipher.cache_clear()
        with self.assertRaises(RuntimeError) as error: cipher()
        self.assertNotIn(self.old.decode(),str(error.exception))

    def test_invalid_explicit_source_never_generates_a_replacement_key(self):
        os.environ['DATA_ENCRYPTION_KEYS']=', ,'; cipher.cache_clear()
        with tempfile.TemporaryDirectory() as tmp, patch.object(settings,'STORAGE_DIR',Path(tmp)):
            with self.assertRaises(RuntimeError): cipher()
            self.assertFalse((Path(tmp)/'.data-encryption.key').exists())


if __name__=='__main__': unittest.main()
