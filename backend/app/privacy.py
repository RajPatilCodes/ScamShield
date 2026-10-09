import json
import time
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select, update, delete, func
from .audit import audit
from .database import begin_auth_write
from .models import Analysis
from .ownership import owned_analysis, locked_owner, publish_marker
from .privacy_config import policy, seconds, PURPOSE, NOTICE_VERSION, NOTICE, NOTICE_HASH
from .privacy_models import (ConsentReceipt, PrivacyPreference, PrivacyOperation, PrivacyJob,
                             ExportChunk, DeletionMarker)
from .privacy_rate_limits import check, private_digest
from .recent_auth import consume
from .scoring import analyze
from .sessions import revoke_all_sessions


def rate(owner, scope, ip, limit):
    check(owner.db, scope, owner.user.lifecycle_id, ip, limit)
    # Counts survive rejected grants/inputs; recheck authorization after commit.
    owner.db.commit()
    begin_auth_write(owner.db)
    owner.user, owner.session = locked_owner(owner.db, owner.user.id, owner.user.lifecycle_id, owner.session.id)


def operation(owner, key, name, payload):
    if not key or len(key) > 255:
        raise HTTPException(422, "A bounded Idempotency-Key is required")
    digest = private_digest(f"operation\0{owner.user.lifecycle_id}\0{name}\0{key}")
    fingerprint = private_digest(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    row = owner.db.get(PrivacyOperation, digest)
    if row and row.expires_at > int(time.time()):
        if row.fingerprint != fingerprint:
            raise HTTPException(409, "Idempotency key conflicts with this request")
        return digest, fingerprint, json.loads(row.result)
    if row:
        owner.db.delete(row)
        owner.db.flush()
    return digest, fingerprint, None


def remember(owner, key, fingerprint, result):
    owner.db.add(PrivacyOperation(key=key, lifecycle_id=owner.user.lifecycle_id, fingerprint=fingerprint,
        result=json.dumps(result), expires_at=int(time.time()) + seconds(policy.status_days)))
    owner.db.commit()
    return result


def current_receipt(db, user):
    pref = db.get(PrivacyPreference, user.id)
    row = db.get(ConsentReceipt, pref.receipt_id) if pref and pref.receipt_id else None
    if (row and row.lifecycle_id == user.lifecycle_id and row.granted and row.version == NOTICE_VERSION
        and row.notice_hash == NOTICE_HASH and row.expires_at > int(time.time())):
        return row
    return None


def settings(owner):
    pref = owner.db.get(PrivacyPreference, owner.user.id)
    return {"purpose": PURPOSE, "notice_kind": "product", "notice": NOTICE, "notice_version": NOTICE_VERSION,
            "notice_hash": NOTICE_HASH, "saving_enabled": current_receipt(owner.db, owner.user) is not None,
            "preference_version": pref.version if pref else 0, "analysis_days": policy.analysis_days,
            "export_hours": policy.export_hours, "artifact_hours": policy.artifact_hours,
            "export_max_bytes": policy.export_max_bytes}


def invalidate_exports(db, user):
    jobs = db.scalars(select(PrivacyJob).where(PrivacyJob.lifecycle_id == user.lifecycle_id, PrivacyJob.kind == "export",
                                             PrivacyJob.state.in_(["queued", "retrying", "ready"])))
    for job in jobs:
        from .privacy_jobs import remove_batch, finish
        remove_batch(db, ExportChunk, ExportChunk.job_id == job.id)
        finish(db, job, "cancelled", "lifecycle_changed")
    user.privacy_revision += 1


def change_consent(owner, purpose, body, key):
    if purpose != PURPOSE or body.version != NOTICE_VERSION:
        raise HTTPException(422, "Unknown purpose or notice version")
    op, fingerprint, previous = operation(owner, key, "consent", {"purpose": purpose, **body.model_dump()})
    if previous is not None:
        return previous
    pref = owner.db.get(PrivacyPreference, owner.user.id)
    if (pref.version if pref else 0) != body.expected_version:
        raise HTTPException(409, "Privacy preference version changed")
    now = int(time.time())
    row = ConsentReceipt(user_id=owner.user.id, lifecycle_id=owner.user.lifecycle_id, purpose=purpose,
        version=NOTICE_VERSION, notice_hash=NOTICE_HASH, granted=body.granted,
        created_at=now, expires_at=now + seconds(policy.consent_days))
    owner.db.add(row)
    owner.db.flush()
    if pref is None:
        pref = PrivacyPreference(user_id=owner.user.id, lifecycle_id=owner.user.lifecycle_id, version=0)
        owner.db.add(pref)
    pref.version += 1
    pref.receipt_id = row.id
    invalidate_exports(owner.db, owner.user)
    audit(owner.db, owner.user.lifecycle_id, "consent_changed", row.id)
    return remember(owner, op, fingerprint, {"saving_enabled": body.granted, "preference_version": pref.version})


def save(owner, body, key):
    op, fingerprint, previous = operation(owner, key, "save", body.model_dump())
    if previous is not None:
        row = owned_analysis(owner, previous["id"])
        if row.record_key != previous["record_key"]:
            raise HTTPException(404, "Private object not found")
        return {**previous, "content": row.content}
    receipt = current_receipt(owner.db, owner.user)
    if receipt is None:
        raise HTTPException(403, "Valid current saving consent is required")
    score, verdict, flags = analyze(body.content)
    now = int(time.time())
    row = Analysis(user_id=owner.user.id, lifecycle_id=owner.user.lifecycle_id, generation=owner.user.data_generation,
        content=body.content, score=score, verdict=verdict, created_at=datetime.fromtimestamp(now, timezone.utc).replace(tzinfo=None),
        expires_at=now + seconds(policy.analysis_days), provenance="current_consent", consent_id=receipt.id)
    owner.db.add(row)
    owner.db.flush()
    audit(owner.db, owner.user.lifecycle_id, "analysis_saved", row.record_key)
    result = serialize_analysis(row)
    result["flags"] = flags
    # Idempotency stores only bounded result metadata, never duplicate raw content.
    stored = {k: v for k, v in result.items() if k != "content"}
    remember(owner, op, fingerprint, stored)
    return result


def serialize_analysis(row):
    return {"id": row.id, "record_key": row.record_key, "content": row.content, "score": row.score,
            "verdict": row.verdict, "flags": [], "saved": True, "created_at": row.created_at.isoformat(),
            "expires_at": row.expires_at, "provenance": row.provenance}


def job_status(job):
    state = job.state
    now = int(time.time())
    if job.kind == "export" and state in ("queued", "retrying", "ready") and (
        job.staging_expires_at <= now or (job.source_expires_at is not None and job.source_expires_at <= now)):
        state = "expired"
    return {"id": job.id, "kind": job.kind, "state": state, "created_at": job.created_at,
            "retry_count": job.retry_count, "next_attempt_at": job.next_attempt_at,
            "finished_at": job.finished_at, "staging_expires_at": job.staging_expires_at,
            "error_code": job.error_code, "total_bytes": job.total_bytes}


def owned_job(owner, job_id, kind):
    row = owner.db.scalar(select(PrivacyJob).where(PrivacyJob.id == job_id, PrivacyJob.user_id == owner.user.id,
        PrivacyJob.lifecycle_id == owner.user.lifecycle_id, PrivacyJob.kind == kind))
    if not row or (row.status_expires_at is not None and row.status_expires_at <= int(time.time())):
        raise HTTPException(404, "Private object not found")
    return row


def create_export(owner, body, key, ip):
    rate(owner, "export_create", ip, policy.export_create_limit)
    op, fingerprint, previous = operation(owner, key, "export", {})
    if previous is not None:
        return job_status(owned_job(owner, previous["id"], "export"))
    now = int(time.time())
    active = owner.db.scalars(select(PrivacyJob).where(PrivacyJob.lifecycle_id == owner.user.lifecycle_id,
        PrivacyJob.kind == "export", PrivacyJob.state.in_(["queued", "retrying", "ready"]),
        (PrivacyJob.source_expires_at.is_(None) | (PrivacyJob.source_expires_at > now)),
        PrivacyJob.staging_expires_at > now)).all()
    if len(active) >= policy.account_export_jobs:
        raise HTTPException(409, "An export is already active")
    consume(owner, body.grant, "export_create", "self")
    row = PrivacyJob(user_id=owner.user.id, lifecycle_id=owner.user.lifecycle_id, revision=owner.user.privacy_revision,
        generation=owner.user.data_generation, kind="export", created_at=now, next_attempt_at=now,
        analysis_boundary=owner.db.scalar(select(func.coalesce(func.max(Analysis.id), 0)).where(Analysis.lifecycle_id == owner.user.lifecycle_id)),
        staging_expires_at=now + policy.export_hours * 3600)
    owner.db.add(row)
    owner.db.flush()
    audit(owner.db, owner.user.lifecycle_id, "export_requested", row.id)
    return remember(owner, op, fingerprint, job_status(row))


def deletion_job(owner, scope, target=None, receipt=None):
    now = int(time.time())
    marker = DeletionMarker(user_id=owner.user.id, lifecycle_id=owner.user.lifecycle_id, scope=scope,
        generation=owner.user.data_generation, revision=owner.user.privacy_revision, target_key=target, created_at=now)
    owner.db.add(marker)
    owner.db.flush()
    row = PrivacyJob(user_id=owner.user.id, lifecycle_id=owner.user.lifecycle_id, revision=owner.user.privacy_revision,
        generation=marker.generation, kind="deletion", marker_id=marker.id, created_at=now, next_attempt_at=now,
        receipt_digest=private_digest(receipt) if receipt else None)
    owner.db.add(row)
    owner.db.flush()
    audit(owner.db, owner.user.lifecycle_id, "deletion_requested", row.id)
    publish_marker(owner.db, marker)
    return row


def delete_one(owner, analysis_id, body, key, ip):
    rate(owner, "deletion", ip, policy.deletion_limit)
    op, fingerprint, previous = operation(owner, key, "delete_analysis", {"id": analysis_id, **body.model_dump()})
    if previous is not None:
        return previous
    row = owned_analysis(owner, analysis_id)
    if row.record_key != body.record_key:
        raise HTTPException(404, "Private object not found")
    row.deleted_at = int(time.time())
    invalidate_exports(owner.db, owner.user)
    job = deletion_job(owner, "analysis", row.record_key)
    audit(owner.db, owner.user.lifecycle_id, "analysis_deleted", row.record_key)
    return remember(owner, op, fingerprint, job_status(job))


def delete_data(owner, body, key, ip):
    rate(owner, "deletion", ip, policy.deletion_limit)
    op, fingerprint, previous = operation(owner, key, "delete_data", {"scope": body.scope, "receipt": body.receipt})
    if previous is not None:
        return previous
    if body.scope == "account" and not body.receipt:
        raise HTTPException(422, "A protected deletion-status receipt is required")
    consume(owner, body.grant, "delete_account" if body.scope == "account" else "delete_saved", "self")
    invalidate_exports(owner.db, owner.user)
    row = deletion_job(owner, body.scope, receipt=body.receipt)
    owner.user.data_generation += 1
    if body.scope == "account":
        owner.user.is_active = False
        owner.user.privacy_state = "deleting"
        revoke_all_sessions(owner.db, owner.user.id)
        # Capture is synthetic/nonproduction and process-local; never logged/exported.
        from .email_delivery import captures
        captures[:] = [message for message in captures if message.recipient != owner.user.email]
    return remember(owner, op, fingerprint, job_status(row))
