"""Revocable opaque sessions. No browser-readable bearer token or legacy JWTs."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

import bcrypt
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import case, delete, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models import AuthSession, AuthThrottle, SensitiveGrant, User, AuditLog

SESSION_COOKIE = '__Host-cdoc_session' if settings.CLOUD_MODE else 'cdoc_session'
SAFE = {'GET', 'HEAD', 'OPTIONS'}


def hash_password(password: str) -> str:
    if len(password.encode()) > 72:
        raise HTTPException(422, '비밀번호는 UTF-8 기준 72바이트 이하여야 합니다.')
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return len(password.encode()) <= 72 and bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def csrf_token(token: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), ('csrf:' + token).encode(), hashlib.sha256).hexdigest()


def check_origin(request: Request):
    origin = request.headers.get('origin')
    allowed = {str(request.base_url).rstrip('/'), *settings.CORS_ORIGINS}
    if origin and origin.rstrip('/') not in allowed:
        raise HTTPException(403, '허용되지 않은 요청 출처입니다.')
    if request.headers.get('sec-fetch-site') == 'cross-site':
        raise HTTPException(403, '다른 사이트에서 보낸 요청은 허용하지 않습니다.')


def create_access_token(user_id: int, db: Session) -> str:
    """Server helper. Raw token is only placed in an HttpOnly cookie."""
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(token_hash=digest(token), user_id=user_id,
                       expires_at=datetime.utcnow() + timedelta(hours=min(settings.ACCESS_TOKEN_HOURS, 8))))
    db.flush()
    return token


def set_session_cookie(response: Response, token: str):
    response.set_cookie(SESSION_COOKIE, token, httponly=True, secure=settings.CLOUD_MODE,
                        samesite='strict', path='/', max_age=min(settings.ACCESS_TOKEN_HOURS, 8) * 3600)
    response.headers['Cache-Control'] = 'no-store'


def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get(SESSION_COOKIE, '')
    session = db.get(AuthSession, digest(token)) if token else None
    if not session or session.expires_at <= datetime.utcnow():
        raise HTTPException(401, '로그인이 필요하거나 세션이 만료되었습니다.')
    if request.method not in SAFE:
        check_origin(request)
        if not hmac.compare_digest(request.headers.get('X-CSRF-Token', ''), csrf_token(token)):
            raise HTTPException(403, '요청 검증에 실패했습니다. 다시 로그인하세요.')
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(401, '로그인이 필요합니다.')
    request.state.auth_session = session
    return user


def throttle(db: Session, request: Request, purpose: str, identity: str):
    """Atomic shared DB counters across serverless instances. No passwords/IPs stored."""
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    now = datetime.utcnow()
    start = now - timedelta(minutes=15)
    insert = pg_insert if db.bind.dialect.name == 'postgresql' else sqlite_insert
    for subject, limit in (('account:' + identity.casefold(), 10),
                           ('ip:' + (request.client.host if request.client else 'unknown'), 60)):
        key = hmac.new(settings.SECRET_KEY.encode(), (purpose + subject).encode(), hashlib.sha256).hexdigest()
        db.execute(insert(AuthThrottle).values(key=key, window_start=now, attempts=0).on_conflict_do_nothing())
        count = db.scalar(update(AuthThrottle).where(AuthThrottle.key == key).values(
            attempts=case((AuthThrottle.window_start < start, 1), else_=AuthThrottle.attempts + 1),
            window_start=case((AuthThrottle.window_start < start, now), else_=AuthThrottle.window_start)
        ).returning(AuthThrottle.attempts))
        db.commit()
        if count > limit:
            raise HTTPException(429, '시도 횟수를 초과했습니다. 15분 후 다시 시도하세요.', headers={'Retry-After': '900'})


def require_sensitive(request: Request, db: Session, user: User, scope: str):
    session = getattr(request.state, 'auth_session', None)
    raw = request.headers.get('X-Sensitive-Grant', '')
    if session and raw:
        consumed = db.scalar(delete(SensitiveGrant).where(
            SensitiveGrant.token_hash == digest(raw), SensitiveGrant.session_hash == session.token_hash,
            SensitiveGrant.scope == scope, SensitiveGrant.expires_at > datetime.utcnow()
        ).returning(SensitiveGrant.token_hash))
        if consumed:
            db.add(AuditLog(user_id=user.id, action='sensitive_use', detail=scope))
            db.commit()
            if scope.startswith(("document:", "contract:")):
                from app.core.render_security import seal_authorized
                seal_authorized.set(True)
            return
    raise HTTPException(403, '인감 사용 또는 보안 설정 변경을 위해 비밀번호를 다시 확인하세요.',
                        headers={'X-Reauthentication-Scope': scope})
