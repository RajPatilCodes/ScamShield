import hashlib
import hmac
import time
from fastapi import HTTPException
from sqlalchemy import select, text
from .config import settings
from .privacy_config import policy
from .privacy_models import PrivacyRateBucket


def private_digest(value):
    return hmac.new(settings.jwt_secret.encode(), b"privacy-v1\0" + value.encode(), hashlib.sha256).hexdigest()


def check(db, scope, lifecycle_id, ip, limit, record=True):
    now = int(time.time())
    key = private_digest(f"rate\0{scope}\0{lifecycle_id}\0{ip}")
    if db.bind.dialect.name == "postgresql":
        lock = int.from_bytes(bytes.fromhex(key)[:8], "big", signed=True)
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock})
    row = db.scalar(select(PrivacyRateBucket).where(PrivacyRateBucket.key == key).with_for_update())
    if row and row.expires_at > now and row.attempts >= limit:
        raise HTTPException(429, "Privacy operation limit reached", headers={"Retry-After": str(row.expires_at - now)})
    if record:
        if not row:
            row = PrivacyRateBucket(key=key, attempts=0, expires_at=now + policy.rate_window_seconds)
            db.add(row)
        if row.expires_at <= now:
            row.attempts = 0
            row.expires_at = now + policy.rate_window_seconds
        row.attempts += 1
        db.flush()
