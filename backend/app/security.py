import time
from uuid import UUID, uuid4

import bcrypt
import jwt
from argon2 import PasswordHasher, Type, extract_parameters
from argon2.exceptions import Argon2Error
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import AuthSession, User

pwd_hasher = PasswordHasher(type=Type.ID, time_cost=settings.argon2_time_cost,
                           memory_cost=settings.argon2_memory_cost, parallelism=settings.argon2_parallelism)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/login")


def hash_password(password: str) -> str:
    return pwd_hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        if hashed.startswith(("$2a$", "$2b$", "$2y$")):
            encoded = password.encode("utf-8")
            # A legacy truncated hash cannot prove ownership of a longer password.
            return len(encoded) <= 72 and bcrypt.checkpw(encoded, hashed.encode("ascii"))
        if hashed.startswith("$argon2id$"):
            return pwd_hasher.verify(hashed, password)
    except (Argon2Error, ValueError, UnicodeError):
        pass
    return False


def password_needs_rehash(hashed: str) -> bool:
    if not hashed.startswith("$argon2id$"):
        return True
    previous = extract_parameters(hashed)
    # Explicit cost changes must never silently downgrade a stronger stored hash.
    at_least_as_strong = (pwd_hasher.time_cost >= previous.time_cost and
                         pwd_hasher.memory_cost >= previous.memory_cost and
                         pwd_hasher.hash_len >= previous.hash_len and
                         pwd_hasher.salt_len >= previous.salt_len)
    return at_least_as_strong and pwd_hasher.check_needs_rehash(hashed)


def create_token(user_id: int, session_id: str) -> str:
    now = int(time.time())
    return jwt.encode({"sub": str(user_id), "sid": session_id, "jti": str(uuid4()),
                       "iat": now, "nbf": now, "exp": now + 600,
                       "iss": settings.jwt_issuer, "aud": settings.jwt_audience,
                       "purpose": "access"}, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"],
                         issuer=settings.jwt_issuer, audience=settings.jwt_audience,
                         options={"require": ["sub", "sid", "jti", "iat", "nbf", "exp", "iss", "aud", "purpose"]})
    if payload["purpose"] != "access" or not isinstance(payload["sub"], str):
        raise ValueError("Invalid credential purpose/identity")
    user_id = int(payload["sub"])
    if user_id <= 0 or str(user_id) != payload["sub"]:
        raise ValueError("Invalid subject")
    for claim in ("sid", "jti"):
        if not isinstance(payload[claim], str) or str(UUID(payload[claim])) != payload[claim]:
            raise ValueError("Invalid credential identifier")
    if any(type(payload[claim]) is not int for claim in ("iat", "nbf", "exp")):
        raise ValueError("Invalid credential timing")
    if not payload["iat"] <= payload["nbf"] < payload["exp"] or payload["exp"] - payload["iat"] > 600:
        raise ValueError("Invalid credential timing")
    return payload


def current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    error = HTTPException(status_code=401, detail="Invalid or expired token")
    try:
        payload = decode_access_token(token)
    except (jwt.PyJWTError, KeyError, ValueError, TypeError, OverflowError):
        raise error from None
    user = db.get(User, int(payload["sub"]))
    session = db.get(AuthSession, payload["sid"])
    now = int(time.time())
    if not user or not user.is_active or not user.email_verified or not session or session.user_id != user.id or session.revoked_at is not None or min(session.idle_expires_at, session.absolute_expires_at) <= now:
        raise error
    return user
