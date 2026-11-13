"""Opaque, revocable server-side sessions; credentials never enter logs."""
import hashlib
import hmac
import secrets
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyCookie
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.prices import get_session
from app.sale_models import AuthThrottle, SaleSession, SaleUser, now

DB = Annotated[Session, Depends(get_session)]
COOKIE = 'samay_session'
session_cookie = APIKeyCookie(name=COOKIE, auto_error=False)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(password):
    salt = secrets.token_hex(16)
    result = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 600_000).hex()
    return f'pbkdf2_sha256$600000${salt}${result}'


def password_valid(password, encoded):
    try:
        _, rounds, salt, expected = encoded.split('$')
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), int(rounds)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def write_guard(request: Request):
    from app.config import get_settings
    if not get_settings().marketplace_enabled:
        raise HTTPException(503, 'marketplace_requires_durable_database')
    # Requiring a non-simple header blocks cross-site form submissions. CORS is restricted.
    if request.method not in {'GET', 'HEAD', 'OPTIONS'} and request.headers.get('X-SAMAY-Action') != '1':
        raise HTTPException(403, 'csrf_header_required')


def current_user(request: Request, db: DB, token: Annotated[str | None, Security(session_cookie)]):
    session = db.get(SaleSession, digest(token)) if token else None
    user = db.get(SaleUser, session.user_id) if session and session.expires_at > now() else None
    if not user or not user.active:
        raise HTTPException(401, 'authentication_required')
    from app.business_service import roles_for
    user.authorized_roles = roles_for(db, user)
    if request.method in {'POST', 'PUT'}:
        throttle(db, f'marketplace-write:{user.id}', 120)
    return user


User = Annotated[SaleUser, Depends(current_user)]


def require_role(user, *roles):
    if not set(getattr(user, 'authorized_roles', [user.role])).intersection(roles):
        raise HTTPException(403, 'role_not_authorized')


def throttle(db, identity, limit=10):
    key = digest(identity)
    row = db.scalar(select(AuthThrottle).where(AuthThrottle.key == key))
    if not row:
        row = AuthThrottle(key=key, attempts=0, reset_at=now() + timedelta(minutes=15))
        db.add(row)
    elif row.reset_at < now():
        row.attempts = 0
        row.reset_at = now() + timedelta(minutes=15)
    if row.attempts >= limit:
        raise HTTPException(429, 'rate_limit_retry_after_15_minutes')
    row.attempts += 1
    db.commit()
