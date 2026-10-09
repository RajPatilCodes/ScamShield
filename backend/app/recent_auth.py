import secrets
import time
from fastapi import HTTPException
from sqlalchemy import select
from .audit import audit
from .privacy_config import policy
from .privacy_models import RecentAuthGrant, PrivacyJob
from .privacy_rate_limits import private_digest, check
from .security import verify_password


def issue(owner, body, ip):
    db, user = owner.db, owner.user
    if body.action == "export_download":
        job = db.scalar(select(PrivacyJob).where(PrivacyJob.id == body.target,
            PrivacyJob.user_id == user.id, PrivacyJob.lifecycle_id == user.lifecycle_id, PrivacyJob.kind == "export"))
        if not job:
            raise HTTPException(404, "Private object not found")
    elif body.target != "self":
        raise HTTPException(422, "Invalid action target")
    check(db, "reauth", user.lifecycle_id, ip, policy.reauth_limit, record=False)
    if not verify_password(body.password, user.password_hash):
        check(db, "reauth", user.lifecycle_id, ip, policy.reauth_limit)
        audit(db, user.lifecycle_id, "reauth_failed")
        db.commit()
        raise HTTPException(403, "Recent authentication failed")
    raw = secrets.token_urlsafe(48)
    now = int(time.time())
    db.add(RecentAuthGrant(digest=private_digest(raw), user_id=user.id, lifecycle_id=user.lifecycle_id,
        session_id=owner.session.id, revision=user.privacy_revision, action=body.action,
        target=body.target, expires_at=now + policy.recent_auth_seconds))
    audit(db, user.lifecycle_id, "reauth_succeeded")
    db.commit()
    return {"grant": raw, "expires_at": now + policy.recent_auth_seconds, "action": body.action, "target": body.target}


def consume(owner, raw, action, target):
    grant = owner.db.scalar(select(RecentAuthGrant).where(RecentAuthGrant.digest == private_digest(raw)).with_for_update())
    now = int(time.time())
    user = owner.user
    if (not grant or grant.user_id != user.id or grant.lifecycle_id != user.lifecycle_id or
        grant.session_id != owner.session.id or grant.revision != user.privacy_revision or
        grant.action != action or grant.target != target or grant.consumed_at is not None or grant.expires_at <= now):
        raise HTTPException(403, "Recent authentication required")
    grant.consumed_at = now
