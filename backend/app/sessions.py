import hashlib
import secrets
import time
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select, update

from .database import begin_auth_write
from .models import AuthSession, RefreshCredential, User
from .schemas import Token
from .security import create_token

IDLE_SECONDS = 7 * 24 * 3600
ABSOLUTE_SECONDS = 30 * 24 * 3600


def credential_digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def issue_credentials(db, session: AuthSession) -> Token:
    raw = secrets.token_urlsafe(48)
    db.add(RefreshCredential(digest=credential_digest(raw), session_id=session.id,
                             expires_at=session.idle_expires_at))
    return Token(access_token=create_token(session.user_id, session.id), refresh_token=raw,
                 session_id=session.id)


def create_session(db, user: User) -> Token:
    now = int(time.time())
    session = AuthSession(id=str(uuid4()), user_id=user.id, created_at=now,
                          idle_expires_at=now + IDLE_SECONDS, absolute_expires_at=now + ABSOLUTE_SECONDS)
    db.add(session)
    db.flush()
    return issue_credentials(db, session)


def rotate_refresh(db, raw: str) -> Token:
    begin_auth_write(db)
    now = int(time.time())
    credential = db.get(RefreshCredential, credential_digest(raw))
    error = HTTPException(status_code=401, detail="Invalid or expired session")
    if credential is None:
        raise error
    session = db.scalar(select(AuthSession).where(AuthSession.id == credential.session_id).with_for_update())
    user = db.get(User, session.user_id) if session else None
    if not session or session.revoked_at is not None:
        raise error
    # Consumed credentials remain recorded for the session family lifetime.
    if credential.consumed_at is not None:
        session.revoked_at = now
        db.commit()
        raise error
    if not user or not user.is_active or not user.email_verified or min(credential.expires_at, session.idle_expires_at, session.absolute_expires_at) <= now:
        raise error
    consumed = db.execute(update(RefreshCredential).where(
        RefreshCredential.digest == credential.digest, RefreshCredential.consumed_at.is_(None)
    ).values(consumed_at=now)).rowcount
    if consumed != 1:
        session.revoked_at = now
        db.commit()
        raise error
    session.idle_expires_at = min(now + IDLE_SECONDS, session.absolute_expires_at)
    token = issue_credentials(db, session)
    db.commit()
    return token


def revoke_all_sessions(db, user_id: int):
    db.execute(update(AuthSession).where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
               .values(revoked_at=int(time.time())))
