import hashlib
import hmac
import time

from fastapi import HTTPException

from .config import settings
from .models import AuthRateBucket

WINDOW_SECONDS = 15 * 60


def bucket_key(scope: str, email: str, ip: str) -> str:
    value = f"{scope}\0{email.lower()}\0{ip}".encode()
    return hmac.new(settings.jwt_secret.encode(), value, hashlib.sha256).hexdigest()


def check_limit(db, scope: str, email: str, ip: str, limit: int):
    if db.bind.dialect.name == "postgresql":
        from sqlalchemy import text
        lock_id = int.from_bytes(bytes.fromhex(bucket_key(scope, email, ip))[:8], "big", signed=True)
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_id})
    bucket = db.get(AuthRateBucket, bucket_key(scope, email, ip))
    if bucket and bucket.expires_at > int(time.time()) and bucket.attempts >= limit:
        raise HTTPException(status_code=429, detail="Try again later", headers={"Retry-After": str(bucket.expires_at - int(time.time()))})


def record_attempt(db, scope: str, email: str, ip: str):
    # Caller holds the auth transaction lock. The bucket is persistent across workers.
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    from sqlalchemy import case
    now = int(time.time())
    insert = sqlite_insert if db.bind.dialect.name == "sqlite" else pg_insert
    query = insert(AuthRateBucket).values(key=bucket_key(scope, email, ip), attempts=1, expires_at=now + WINDOW_SECONDS)
    db.execute(query.on_conflict_do_update(index_elements=[AuthRateBucket.key], set_={
        "attempts": case((AuthRateBucket.expires_at <= now, 1), else_=AuthRateBucket.attempts + 1),
        "expires_at": case((AuthRateBucket.expires_at <= now, now + WINDOW_SECONDS), else_=AuthRateBucket.expires_at),
    }))
