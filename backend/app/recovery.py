import secrets
import time

from fastapi import HTTPException
from sqlalchemy import select, update

from .config import settings
from .email_delivery import deliver_challenge
from .models import AuthChallenge, User
from .security import hash_password
from .sessions import credential_digest, revoke_all_sessions


def send_challenge(db, user: User, purpose: str):
    raw = secrets.token_urlsafe(48)
    minutes = 30 if purpose == "recovery" else settings.verification_expire_minutes
    db.add(AuthChallenge(digest=credential_digest(raw), user_id=user.id, purpose=purpose,
                         expires_at=int(time.time()) + minutes * 60))
    db.flush()
    deliver_challenge(user.email, purpose, raw)


def consume_challenge(db, raw: str, purpose: str, password: str | None = None):
    now = int(time.time())
    challenge = db.scalar(select(AuthChallenge).where(AuthChallenge.digest == credential_digest(raw)).with_for_update())
    error = HTTPException(status_code=400, detail="Invalid or expired challenge")
    if not challenge or challenge.purpose != purpose or challenge.consumed_at is not None or challenge.expires_at <= now:
        raise error
    user = db.scalar(select(User).where(User.id == challenge.user_id).with_for_update())
    if not user or not user.is_active:
        raise error
    consumed = db.execute(update(AuthChallenge).where(AuthChallenge.digest == challenge.digest,
        AuthChallenge.consumed_at.is_(None), AuthChallenge.expires_at > now).values(consumed_at=now)).rowcount
    if consumed != 1:
        raise error
    # Invalidate other outstanding challenges of this purpose as well.
    db.execute(update(AuthChallenge).where(AuthChallenge.user_id == user.id, AuthChallenge.purpose == purpose,
        AuthChallenge.consumed_at.is_(None)).values(consumed_at=now))
    if purpose == "verification":
        user.email_verified = True
    else:
        user.password_hash = hash_password(password)
        revoke_all_sessions(db, user.id)
