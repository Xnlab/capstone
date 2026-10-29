"""RFC 6238 TOTP; secrets encrypted, steps and recovery tokens consumed atomically."""
import base64
import hashlib
import hmac
import re
import secrets
import struct
import time

from fastapi import HTTPException
from sqlalchemy import delete, update

from app.core.security import digest
from app.models import MfaCredential, MfaRecovery


def new_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode()


def totp(secret, step, digits=6):
    mac = hmac.new(base64.b32decode(secret), struct.pack('>Q', step), hashlib.sha1).digest()
    offset = mac[-1] & 15
    number = struct.unpack('>I', mac[offset:offset + 4])[0] & 0x7fffffff
    return str(number % (10 ** digits)).zfill(digits)


def verify_factor(db, credential, code, *, recovery=True):
    code = code.strip()
    if re.fullmatch(r'\d{6}', code, flags=re.ASCII):
        now = int(time.time()) // 30
        for step in (now, now - 1, now + 1):
            if hmac.compare_digest(totp(credential.secret, step), code):
                used = db.scalar(update(MfaCredential).where(
                    MfaCredential.user_id == credential.user_id,
                    MfaCredential.last_step < step,
                    MfaCredential.pending_session == credential.pending_session,
                    MfaCredential.enabled == credential.enabled,
                ).values(last_step=step).returning(MfaCredential.user_id))
                if used is not None:
                    return 'totp'
                break
    elif recovery:
        normalized = code.replace('-', '').upper()
        used = db.scalar(delete(MfaRecovery).where(
            MfaRecovery.user_id == credential.user_id,
            MfaRecovery.code_hash == digest(normalized),
        ).returning(MfaRecovery.code_hash))
        if used:
            return 'recovery'
    raise HTTPException(403, '인증 코드가 올바르지 않거나 이미 사용되었습니다. 새 코드 또는 복구 코드를 입력하세요.')


def recovery_codes(db, user_id):
    db.execute(delete(MfaRecovery).where(MfaRecovery.user_id == user_id))
    codes = [secrets.token_hex(10).upper() for _ in range(8)]
    db.add_all([MfaRecovery(user_id=user_id, code_hash=digest(code)) for code in codes])
    return ['-'.join(code[i:i + 5] for i in range(0, 20, 5)) for code in codes]
