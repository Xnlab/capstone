"""Owner-only MFA management and session-revoking password changes."""
from datetime import datetime, timedelta
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.mfa import new_secret, recovery_codes, verify_factor
from app.core.security import check_origin, digest, get_current_user, hash_password, throttle, verify_password, lock_account
from app.models import AuditLog, AuthSession, MfaChallenge, MfaCredential, MfaRecovery, SensitiveGrant, User
from app.routers.auth import issue

router = APIRouter(prefix='/auth', tags=['account security'])


class Proof(BaseModel):
    password: str = Field(max_length=100)
    code: str = Field(default='', max_length=40)


class ChallengeIn(BaseModel):
    challenge: str = Field(min_length=20, max_length=100)
    code: str = Field(min_length=1, max_length=40)


def credential_for(db, user_id):
    return db.scalar(select(MfaCredential).where(MfaCredential.user_id == user_id).with_for_update().execution_options(populate_existing=True))


def prove(body, request, user, db, *, factor=True):
    throttle(db, request, 'security-change', str(user.id))
    # Refresh after throttle commits so a concurrent credential change cannot use stale state.
    lock_account(db, request, user)
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(403, '비밀번호를 확인하세요.')
    credential = credential_for(db, user.id)
    if factor and credential and credential.enabled:
        verify_factor(db, credential, body.code)
    return credential


def invalidate(db, user_id):
    keys = select(AuthSession.token_hash).where(AuthSession.user_id == user_id)
    db.execute(delete(SensitiveGrant).where(SensitiveGrant.session_hash.in_(keys)))
    db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
    db.execute(delete(MfaChallenge).where(MfaChallenge.user_id == user_id))


@router.post('/mfa/verify')
def login_factor(body: ChallengeIn, request: Request, response: Response, db: Session = Depends(get_db)):
    check_origin(request)
    challenge = db.get(MfaChallenge, digest(body.challenge))
    if not challenge or challenge.expires_at <= datetime.utcnow():
        raise HTTPException(403, '추가 인증이 만료되었습니다. 비밀번호로 다시 로그인하세요.')
    user_id = challenge.user_id
    throttle(db, request, 'mfa-verify', str(user_id))
    db.scalar(select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True))
    credential = credential_for(db, user_id)
    if not credential or not credential.enabled:
        raise HTTPException(403, '다시 로그인하세요.')
    try:
        factor = verify_factor(db, credential, body.code)
    except HTTPException:
        db.rollback()
        db.add(AuditLog(user_id=user_id, action='mfa_failed', detail='추가 인증 실패'))
        db.commit()
        raise
    consumed = db.scalar(delete(MfaChallenge).where(
        MfaChallenge.token_hash == digest(body.challenge),
        MfaChallenge.expires_at > datetime.utcnow(),
    ).returning(MfaChallenge.user_id))
    if consumed is None:
        db.rollback()
        raise HTTPException(403, '이미 사용되었거나 만료된 로그인 요청입니다.')
    if factor == 'recovery':
        invalidate(db, user_id)
        db.add(AuditLog(user_id=user_id, action='mfa_recovered', detail='복구 코드 사용 및 기존 세션 폐기'))
    db.add(AuditLog(user_id=user_id, action='mfa_login', detail='추가 인증 완료'))
    return issue(db, response, request, db.get(User, user_id))


@router.get('/mfa')
def status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    credential = db.get(MfaCredential, user.id)
    return {'enabled': bool(credential and credential.enabled),
            'recovery_remaining': db.scalar(select(func.count()).select_from(MfaRecovery).where(MfaRecovery.user_id == user.id))}


@router.post('/mfa/setup')
def setup(body: Proof, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    credential = prove(body, request, user, db, factor=False)
    if credential and credential.enabled:
        raise HTTPException(409, '이미 설정되어 있습니다. 기존 추가 인증으로 해제한 뒤 다시 등록하세요.')
    if credential is None:
        credential = MfaCredential(user_id=user.id)
        db.add(credential)
    secret = new_secret()
    credential.secret = secret
    credential.enabled = 0
    credential.last_step = -1
    credential.pending_session = request.state.auth_session.token_hash
    credential.pending_expires = datetime.utcnow() + timedelta(minutes=10)
    db.add(AuditLog(user_id=user.id, action='mfa_setup', detail='인증 앱 등록 시작'))
    db.commit()
    # No external QR service: the shared secret stays between this browser and the API.
    return {'secret': secret, 'issuer': 'Capstone', 'account': user.email,
            'uri': f'otpauth://totp/{quote("Capstone:" + user.email, safe="")}?secret={secret}&issuer=Capstone&algorithm=SHA1&digits=6&period=30'}


@router.post('/mfa/enable')
def enable(body: Proof, request: Request, response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    credential = prove(body, request, user, db, factor=False)
    if not credential or credential.enabled or credential.pending_expires <= datetime.utcnow() or credential.pending_session != request.state.auth_session.token_hash:
        raise HTTPException(409, '이 기기에서 인증 앱 등록을 다시 시작하세요.')
    verify_factor(db, credential, body.code, recovery=False)
    credential.enabled = 1
    codes = recovery_codes(db, user.id)
    invalidate(db, user.id)
    db.add(AuditLog(user_id=user.id, action='mfa_enabled', detail='2단계 인증 설정 및 기존 세션 폐기'))
    result = issue(db, response, request, user)
    return {**result, 'recovery_codes': codes}


@router.post('/mfa/disable')
def disable(body: Proof, request: Request, response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    credential = prove(body, request, user, db)
    if not credential or not credential.enabled:
        raise HTTPException(409, '2단계 인증이 설정되어 있지 않습니다.')
    db.delete(credential)
    db.execute(delete(MfaRecovery).where(MfaRecovery.user_id == user.id))
    invalidate(db, user.id)
    db.add(AuditLog(user_id=user.id, action='mfa_disabled', detail='2단계 인증 해제 및 기존 세션 폐기'))
    return issue(db, response, request, user)


@router.post('/mfa/recovery')
def regenerate(body: Proof, request: Request, response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    credential = prove(body, request, user, db)
    if not credential or not credential.enabled:
        raise HTTPException(409, '먼저 2단계 인증을 설정하세요.')
    codes = recovery_codes(db, user.id)
    invalidate(db, user.id)
    db.add(AuditLog(user_id=user.id, action='mfa_recovery', detail='복구 코드 교체 및 기존 세션 폐기'))
    return {**issue(db, response, request, user), 'recovery_codes': codes}


class PasswordIn(Proof):
    new_password: str = Field(min_length=12, max_length=100)


@router.post('/password')
def change_password(body: PasswordIn, request: Request, response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prove(body, request, user, db)
    if body.new_password == body.password:
        raise HTTPException(422, '다른 비밀번호를 입력하세요.')
    user.password_hash = hash_password(body.new_password)
    invalidate(db, user.id)
    db.add(AuditLog(user_id=user.id, action='password_changed', detail='비밀번호 변경 및 기존 세션 폐기'))
    return issue(db, response, request, user)
