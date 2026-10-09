"""Transactional, bounded privacy work. No external queue or evidence worker."""
import json
import time
from datetime import datetime, timezone
from sqlalchemy import select, delete, func, text, exists
from fastapi import HTTPException
from .audit import audit
from .database import begin_auth_write, SessionLocal
from .models import User, Analysis, AuthSession, RefreshCredential, AuthChallenge, AuthRateBucket
from .ownership import locked_owner, visible_analysis, require_authority, publish_marker, AuthorityUnavailable
from .privacy_config import policy, seconds
from .privacy_models import (PrivacyJob, ExportChunk, DeletionMarker, ConsentReceipt, PrivacyPreference,
                             PrivacyOperation, RecentAuthGrant, AuditEvent, PrivacyRateBucket)
from .privacy_rate_limits import private_digest


def finish(db, job, state, code=None):
    now = int(time.time())
    job.state = state
    job.error_code = code
    if job.finished_at is None:
        job.finished_at = now
        job.status_expires_at = now + seconds(policy.status_days)
    audit(db, job.lifecycle_id, "job_completed" if state == "completed" else "job_failed", job.id)


def stage(db, job, records):
    payload = b"".join((json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8") for record in records)
    if job.total_bytes + len(payload) > policy.export_max_bytes:
        raise ValueError("export_limit")
    ordinal = db.scalar(select(func.coalesce(func.max(ExportChunk.ordinal), -1)).where(ExportChunk.job_id == job.id)) + 1
    # Derive a byte bound from the approved size and batch inputs; no new limit.
    chunk_bytes = max(1, policy.export_max_bytes // policy.batch_size)
    for offset in range(0, len(payload), chunk_bytes):
        db.add(ExportChunk(job_id=job.id, ordinal=ordinal, payload=payload[offset:offset + chunk_bytes]))
        ordinal += 1
    job.total_bytes += len(payload)


def export_batch(db, job, user):
    now = int(time.time())
    if (not user or not user.is_active or user.privacy_state != "active" or user.lifecycle_id != job.lifecycle_id
        or user.privacy_revision != job.revision or user.data_generation != job.generation):
        remove_batch(db, ExportChunk, ExportChunk.job_id == job.id)
        finish(db, job, "cancelled", "lifecycle_changed")
        return
    if job.staging_expires_at <= now or (job.source_expires_at is not None and job.source_expires_at <= now):
        remove_batch(db, ExportChunk, ExportChunk.job_id == job.id)
        finish(db, job, "expired", "export_expired")
        return
    if job.phase == "restart":
        # A failed export may have had chunks removed by maintenance. Rebuild
        # from its original source boundary only after bounded cleanup finishes.
        if remove_batch(db, ExportChunk, ExportChunk.job_id == job.id):
            return
        job.total_bytes = job.cursor = 0
        job.cursor_key = ""
        job.phase = "start"
    if job.phase == "start":
        stage(db, job, [{"type": "manifest", "format_version": 1, "created_at": job.created_at},
            {"type": "account", "email": user.email, "created_at": user.created_at.isoformat()}])
        job.phase = "analyses"
    elif job.phase == "analyses":
        rows = db.scalars(select(Analysis).where(*visible_analysis(user), Analysis.id > job.cursor, Analysis.id <= job.analysis_boundary,
            Analysis.created_at <= datetime.fromtimestamp(job.created_at, timezone.utc).replace(tzinfo=None))
            .order_by(Analysis.id).limit(policy.batch_size)).all()
        if rows:
            stage(db, job, [{"type": "analysis", "id": row.id, "content": row.content, "score": row.score,
                "verdict": row.verdict, "created_at": row.created_at.isoformat(), "expires_at": row.expires_at,
                "provenance": row.provenance} for row in rows])
            job.cursor = rows[-1].id
            expiry = min(row.expires_at for row in rows)
            job.source_expires_at = min(job.source_expires_at or expiry, expiry)
        else:
            job.phase = "consents"
    elif job.phase == "consents":
        rows = db.scalars(select(ConsentReceipt).where(ConsentReceipt.lifecycle_id == job.lifecycle_id,
            ConsentReceipt.id > job.cursor_key, ConsentReceipt.created_at <= job.created_at, ConsentReceipt.expires_at > now)
            .order_by(ConsentReceipt.id).limit(policy.batch_size)).all()
        if rows:
            stage(db, job, [{"type": "consent", "purpose": row.purpose, "version": row.version,
                "granted": row.granted, "created_at": row.created_at, "expires_at": row.expires_at} for row in rows])
            job.cursor_key = rows[-1].id
            expiry = min(row.expires_at for row in rows)
            job.source_expires_at = min(job.source_expires_at or expiry, expiry)
        else:
            job.phase, job.cursor_key = "sessions", ""
    elif job.phase == "sessions":
        rows = db.scalars(select(AuthSession).where(AuthSession.user_id == user.id, AuthSession.id > job.cursor_key,
            AuthSession.created_at <= job.created_at, AuthSession.absolute_expires_at > now)
            .order_by(AuthSession.id).limit(policy.batch_size)).all()
        if rows:
            stage(db, job, [{"type": "session_metadata", "created_at": row.created_at,
                "idle_expires_at": row.idle_expires_at, "absolute_expires_at": row.absolute_expires_at,
                "revoked_at": row.revoked_at} for row in rows])
            job.cursor_key = rows[-1].id
        else:
            job.phase, job.cursor_key = "audit", ""
    elif job.phase == "audit":
        rows = db.scalars(select(AuditEvent).where(AuditEvent.lifecycle_id == job.lifecycle_id,
            AuditEvent.id > job.cursor_key, AuditEvent.created_at <= job.created_at, AuditEvent.expires_at > now)
            .order_by(AuditEvent.id).limit(policy.batch_size)).all()
        if rows:
            stage(db, job, [{"type": "audit", "event": row.event, "created_at": row.created_at} for row in rows])
            job.cursor_key = rows[-1].id
            expiry = min(row.expires_at for row in rows)
            job.source_expires_at = min(job.source_expires_at or expiry, expiry)
        else:
            stage(db, job, [{"type": "end", "complete": True}])
            job.state = "ready"
            if job.finished_at is None:
                job.finished_at = now
                job.status_expires_at = now + seconds(policy.status_days)
            audit(db, job.lifecycle_id, "job_completed", job.id)


def remove_batch(db, model, condition):
    rows = db.scalars(select(model).where(condition).limit(policy.batch_size)).all()
    for row in rows:
        db.delete(row)
    db.flush()
    return len(rows)


def deletion_batch(db, job, user):
    marker = db.get(DeletionMarker, job.marker_id)
    if marker is None:
        raise ValueError("missing_deletion_intent")
    if marker.satisfied_at is not None:
        finish(db, job, "completed")
        return
    same = user is not None and user.lifecycle_id == marker.lifecycle_id
    if marker.scope == "analysis":
        remove_batch(db, Analysis, (Analysis.lifecycle_id == marker.lifecycle_id) & (Analysis.record_key == marker.target_key))
    elif marker.scope == "saved":
        if remove_batch(db, Analysis, (Analysis.lifecycle_id == marker.lifecycle_id) & (Analysis.generation <= marker.generation)):
            return
    else:
        if same and user.is_active:
            raise ValueError("account_not_restricted")
        # Do not hold a User lock while removing auth children: recovery locks challenge then User.
        for model in (Analysis, ConsentReceipt, PrivacyPreference, RecentAuthGrant, PrivacyOperation):
            if remove_batch(db, model, model.lifecycle_id == marker.lifecycle_id):
                return
        exports = db.scalars(select(PrivacyJob).where(PrivacyJob.lifecycle_id == marker.lifecycle_id,
            PrivacyJob.kind == "export", (PrivacyJob.state.in_(["queued", "retrying", "ready"]) |
            exists(select(ExportChunk.job_id).where(ExportChunk.job_id == PrivacyJob.id)))).limit(policy.batch_size)).all()
        for export in exports:
            if remove_batch(db, ExportChunk, ExportChunk.job_id == export.id):
                return
            if export.state in ("queued", "retrying", "ready"):
                finish(db, export, "cancelled", "account_deleted")
        if same:
            if remove_batch(db, AuthChallenge, AuthChallenge.user_id == marker.user_id):
                return
            session_ids = select(AuthSession.id).where(AuthSession.user_id == marker.user_id)
            if remove_batch(db, RefreshCredential, RefreshCredential.session_id.in_(session_ids)):
                return
            if remove_batch(db, AuthSession, AuthSession.user_id == marker.user_id):
                return
            db.delete(user)
    marker.satisfied_at = int(time.time())
    finish(db, job, "completed")
    publish_marker(db, marker)


def fail_job(db, job_id, permanent=False):
    begin_auth_write(db)
    require_authority(db)
    job = db.scalar(select(PrivacyJob).where(PrivacyJob.id == job_id).with_for_update())
    if job is None or job.state not in ("queued", "retrying"):
        db.rollback()
        return
    marker = db.get(DeletionMarker, job.marker_id) if job.marker_id else None
    attempts = marker.retry_count if marker else job.retry_count
    if permanent or attempts >= policy.automatic_retries:
        finish(db, job, "failed", "export_size_limit" if permanent else "processing_failed")
        if marker:
            marker.exhausted = True
        remove_batch(db, ExportChunk, ExportChunk.job_id == job.id)
    else:
        delay = min(policy.retry_initial_seconds * 2 ** attempts, policy.retry_max_seconds)
        job.retry_count = attempts + 1
        if marker:
            marker.retry_count = job.retry_count
        job.state = "retrying"
        job.next_attempt_at = int(time.time()) + delay
        job.error_code = "processing_retry"
    if marker:
        publish_marker(db, marker)
    db.commit()


def process_job(job_id, factory=SessionLocal):
    with factory() as db:
        try:
            begin_auth_write(db)
            require_authority(db)
            lookup = db.get(PrivacyJob, job_id)
            if not lookup or lookup.state not in ("queued", "retrying") or lookup.next_attempt_at > int(time.time()):
                db.rollback()
                return False
            user = db.scalar(select(User).where(User.id == lookup.user_id, User.lifecycle_id == lookup.lifecycle_id))
            marker = db.get(DeletionMarker, lookup.marker_id) if lookup.marker_id else None
            # Active-account work uses account-first ordering. Restricted-account child purge deliberately does not.
            if user and user.is_active:
                user, _ = locked_owner(db, user.id, user.lifecycle_id)
            job = db.scalar(select(PrivacyJob).where(PrivacyJob.id == job_id).with_for_update(skip_locked=True)
                            .execution_options(populate_existing=True))
            if (job is None or job.state not in ("queued", "retrying")
                    or job.next_attempt_at > int(time.time())):
                db.rollback()
                return False
            if job.kind == "export":
                if db.bind.dialect.name == "postgresql":
                    slot = False
                    for index in range(policy.global_export_jobs):
                        key = int.from_bytes(bytes.fromhex(private_digest(f"export-slot-{index}"))[:8], "big", signed=True)
                        if db.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": key}):
                            slot = True
                            break
                    if not slot:
                        db.rollback()
                        return False
                export_batch(db, job, user)
            else:
                deletion_batch(db, job, user)
            db.commit()
            return True
        except Exception as error:
            db.rollback()
            if isinstance(error, AuthorityUnavailable):
                raise
            fail_job(db, job_id, permanent=isinstance(error, ValueError) and str(error) == "export_limit")
            return False


def retry_marker(db, marker_id):
    begin_auth_write(db)
    require_authority(db)
    marker = db.scalar(select(DeletionMarker).where(DeletionMarker.id == marker_id).with_for_update())
    if not marker or marker.satisfied_at is not None:
        raise ValueError("No unresolved deletion intent")
    active = db.scalar(select(PrivacyJob).where(PrivacyJob.marker_id == marker.id, PrivacyJob.state.in_(["queued", "retrying"])))
    if active:
        db.rollback()
        return active.id
    user = db.scalar(select(User).where(User.id == marker.user_id, User.lifecycle_id == marker.lifecycle_id))
    now = int(time.time())
    job = PrivacyJob(user_id=marker.user_id, lifecycle_id=marker.lifecycle_id, revision=user.privacy_revision if user else 0,
        generation=marker.generation, kind="deletion", marker_id=marker.id, retry_count=marker.retry_count,
        created_at=now, next_attempt_at=now)
    db.add(job)
    db.flush()
    audit(db, marker.lifecycle_id, "job_retried", job.id)
    db.commit()
    return job.id


def retry_job(db, job_id):
    """Operator retry with original authority, source, deadlines and retry budget."""
    begin_auth_write(db)
    require_authority(db)
    lookup = db.get(PrivacyJob, job_id)
    if lookup is None:
        raise ValueError("No retained failed privacy job")
    if lookup.kind == "deletion":
        return retry_marker(db, lookup.marker_id)
    user, _ = locked_owner(db, lookup.user_id, lookup.lifecycle_id)
    job = db.scalar(select(PrivacyJob).where(PrivacyJob.id == job_id).with_for_update()
                    .execution_options(populate_existing=True))
    now = int(time.time())
    if (job.state != "failed" or job.status_expires_at <= now or job.staging_expires_at <= now
            or (job.source_expires_at is not None and job.source_expires_at <= now)
            or job.revision != user.privacy_revision or job.generation != user.data_generation):
        raise ValueError("No eligible failed export")
    active = db.scalar(select(PrivacyJob.id).where(PrivacyJob.lifecycle_id == job.lifecycle_id,
        PrivacyJob.kind == "export", PrivacyJob.id != job.id, PrivacyJob.state.in_(["queued", "retrying", "ready"]),
        PrivacyJob.staging_expires_at > now,
        PrivacyJob.source_expires_at.is_(None) | (PrivacyJob.source_expires_at > now)).limit(1))
    if active:
        raise ValueError("An export is already active")
    job.state, job.phase, job.error_code = "queued", "restart", None
    job.next_attempt_at = now
    audit(db, job.lifecycle_id, "job_retried", job.id)
    db.commit()
    return job.id


def stream_export(job_id, user_id, lifecycle_id, session_id, token, factory=SessionLocal):
    ordinal = 0
    while True:
        with factory() as db:
            begin_auth_write(db)
            from .security import current_user
            current_user(token, db)
            user, _ = locked_owner(db, user_id, lifecycle_id, session_id)
            job = db.get(PrivacyJob, job_id)
            now = int(time.time())
            if (not job or job.lifecycle_id != lifecycle_id or job.user_id != user_id or job.state != "ready"
                or job.revision != user.privacy_revision or job.staging_expires_at <= now
                or (job.source_expires_at is not None and job.source_expires_at <= now)):
                raise HTTPException(410, "Export unavailable")
            chunk = db.get(ExportChunk, (job_id, ordinal))
            payload = chunk.payload if chunk else None
            db.commit()
        if payload is None:
            return
        yield payload
        ordinal += 1


def sweep(db):
    begin_auth_write(db)
    require_authority(db)
    now = int(time.time())
    stats = {}
    for model in (ConsentReceipt, AuditEvent, RecentAuthGrant, PrivacyOperation, PrivacyRateBucket, AuthRateBucket):
        stats[model.__tablename__] = remove_batch(db, model, model.expires_at <= now)
    stats["analyses"] = remove_batch(db, Analysis, Analysis.expires_at <= now)
    jobs = db.scalars(select(PrivacyJob).where((PrivacyJob.staging_expires_at <= now) |
        (PrivacyJob.source_expires_at <= now) | PrivacyJob.state.in_(["cancelled", "failed", "expired"]))
        .where(PrivacyJob.state.in_(["queued", "retrying", "ready"]) |
               exists(select(ExportChunk.job_id).where(ExportChunk.job_id == PrivacyJob.id))).limit(policy.batch_size)).all()
    for job in jobs:
        stats["chunks"] = stats.get("chunks", 0) + remove_batch(db, ExportChunk, ExportChunk.job_id == job.id)
        if job.state in ("queued", "retrying", "ready"):
            finish(db, job, "expired", "export_expired")
            stats["expired_exports"] = stats.get("expired_exports", 0) + 1
    expired = db.scalars(select(PrivacyJob).where(PrivacyJob.status_expires_at <= now).limit(policy.batch_size)).all()
    for job in expired:
        removed = remove_batch(db, ExportChunk, ExportChunk.job_id == job.id)
        stats["chunks"] = stats.get("chunks", 0) + removed
        if removed == 0:
            db.delete(job)
            stats["statuses"] = stats.get("statuses", 0) + 1
    # Replay evidence stays until the Phase 2 absolute family boundary.
    families = select(AuthSession.id).where(AuthSession.absolute_expires_at <= now)
    stats["refresh_credentials"] = remove_batch(db, RefreshCredential, RefreshCredential.session_id.in_(families))
    stats["sessions"] = remove_batch(db, AuthSession, (AuthSession.absolute_expires_at <= now) &
        ~AuthSession.id.in_(select(RefreshCredential.session_id)))
    stats["challenges"] = remove_batch(db, AuthChallenge, AuthChallenge.expires_at <= now)
    # Markers are never age-pruned: authoritative backup/fencing obligations are unresolved.
    db.commit()
    return stats
