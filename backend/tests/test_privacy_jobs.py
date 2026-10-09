import time
from sqlalchemy import select
from app.database import SessionLocal
from app.privacy_config import policy, seconds
from app.privacy_models import PrivacyJob, DeletionMarker, ExportChunk
from app.privacy_jobs import process_job, fail_job, retry_marker, retry_job, sweep
from tests.privacy_helpers import account, headers, consent, save, grant, drain


def test_ready_staging_expiry_does_not_renew_terminal_retention(client, monkeypatch):
    tokens = account(client)
    job = client.post("/v1/privacy/exports", headers=headers(tokens),
        json={"grant": grant(client, tokens, "export_create")}).json()
    assert drain(job["id"]) == "ready"
    with SessionLocal() as db:
        row = db.get(PrivacyJob, job["id"])
        original = (row.finished_at, row.status_expires_at)
        deadline = row.staging_expires_at
    monkeypatch.setattr(time, "time", lambda: deadline)
    with SessionLocal() as db:
        sweep(db)
        row = db.get(PrivacyJob, job["id"])
        assert row.state == "expired"
        assert (row.finished_at, row.status_expires_at) == original
    monkeypatch.setattr(time, "time", lambda: original[1])
    with SessionLocal() as db:
        sweep(db)
        assert db.get(PrivacyJob, job["id"]) is None


def test_deadline_postponed_while_obtaining_owner_lock_prevents_processing(client, monkeypatch):
    import app.privacy_jobs as jobs
    tokens = account(client)
    job = client.post("/v1/privacy/exports", headers=headers(tokens),
        json={"grant": grant(client, tokens, "export_create")}).json()
    original_lock = jobs.locked_owner
    def postpone(db, *args):
        result = original_lock(db, *args)
        db.get(PrivacyJob, job["id"]).next_attempt_at = int(time.time()) + policy.retry_initial_seconds
        db.commit()  # Deterministic equivalent of the competing transaction.
        return result
    monkeypatch.setattr(jobs, "locked_owner", postpone)
    assert process_job(job["id"]) is False
    with SessionLocal() as db:
        row = db.get(PrivacyJob, job["id"])
        assert row.phase == "start" and row.total_bytes == 0 and row.retry_count == 0
        assert row.next_attempt_at > int(time.time())
        assert db.get(ExportChunk, (row.id, 0)) is None


def test_manual_export_retry_preserves_budget_deadlines_and_rebuilds_complete_staging(client):
    import json
    tokens = account(client)
    consent(client, tokens)
    save(client, tokens, "original saved row")
    job = client.post("/v1/privacy/exports", headers=headers(tokens),
        json={"grant": grant(client, tokens, "export_create")}).json()
    assert process_job(job["id"])  # Stage manifest before repeated failures.
    for _ in range(policy.automatic_retries + 1):
        with SessionLocal() as db:
            fail_job(db, job["id"])
    with SessionLocal() as db:
        row = db.get(PrivacyJob, job["id"])
        original = (row.finished_at, row.status_expires_at, row.staging_expires_at, row.created_at)
        assert row.state == "failed" and row.retry_count == 5
        assert retry_job(db, row.id) == row.id
    assert drain(job["id"]) == "ready"
    with SessionLocal() as db:
        row = db.get(PrivacyJob, job["id"])
        assert row.retry_count == 5
        assert (row.finished_at, row.status_expires_at, row.staging_expires_at, row.created_at) == original
        payload = b"".join(db.scalars(select(ExportChunk.payload).where(ExportChunk.job_id == row.id).order_by(ExportChunk.ordinal)))
        records = [json.loads(line) for line in payload.splitlines()]
        assert records[0]["type"] == "manifest" and records[-1] == {"type": "end", "complete": True}
        assert sum(record["type"] == "manifest" for record in records) == 1
        assert any(record.get("content") == "original saved row" for record in records)


def test_manual_export_retry_failure_does_not_create_new_automatic_budget(client):
    tokens = account(client)
    job = client.post("/v1/privacy/exports", headers=headers(tokens),
        json={"grant": grant(client, tokens, "export_create")}).json()
    for _ in range(policy.automatic_retries + 1):
        with SessionLocal() as db:
            fail_job(db, job["id"])
    with SessionLocal() as db:
        retry_job(db, job["id"])
    with SessionLocal() as db:
        fail_job(db, job["id"])
        row = db.get(PrivacyJob, job["id"])
        assert row.state == "failed" and row.retry_count == 5


def test_export_limit_and_capacity(client, monkeypatch):
    tokens = account(client)
    consent(client, tokens)
    save(client, tokens)
    job = client.post("/v1/privacy/exports", headers=headers(tokens), json={"grant": grant(client, tokens, "export_create")}).json()
    assert client.post("/v1/privacy/exports", headers=headers(tokens), json={"grant": grant(client, tokens, "export_create")}).status_code == 409
    monkeypatch.setattr(policy, "export_max_bytes", 1)  # Fault injection, not a production default.
    assert process_job(job["id"]) is False
    with SessionLocal() as db:
        row = db.get(PrivacyJob, job["id"])
        assert row.state == "failed" and row.error_code == "export_size_limit"
        assert db.get(ExportChunk, (job["id"], 0)) is None


def test_persisted_retry_budget_and_manual_retry_after_status_expiry(client):
    tokens = account(client)
    job = client.post("/v1/privacy/deletions", headers=headers(tokens), json={"scope": "saved", "grant": grant(client, tokens, "delete_saved")}).json()
    for attempt in range(6):
        with SessionLocal() as db:
            fail_job(db, job["id"])
            row = db.get(PrivacyJob, job["id"])
            if attempt < 5:
                assert row.retry_count == attempt + 1
                assert row.next_attempt_at == int(time.time()) + min(60 * 2 ** attempt, 3600)
            else:
                assert row.state == "failed"
                marker_id = row.marker_id
                row.status_expires_at = int(time.time())
                db.commit()
    with SessionLocal() as db:
        sweep(db)
        assert db.get(PrivacyJob, job["id"]) is None
        marker = db.get(DeletionMarker, marker_id)
        assert marker is not None and marker.retry_count == 5 and marker.satisfied_at is None
        new = retry_marker(db, marker_id)
    assert drain(new) == "completed"


def test_export_staging_expiry_and_source_delete(client):
    tokens = account(client)
    consent(client, tokens)
    row = save(client, tokens).json()
    job = client.post("/v1/privacy/exports", headers=headers(tokens), json={"grant": grant(client, tokens, "export_create")}).json()
    assert job["staging_expires_at"] == int(time.time()) + 24 * 3600
    assert drain(job["id"]) == "ready"
    deletion = client.request("DELETE", f"/v1/privacy/analyses/{row['id']}", headers=headers(tokens), json={"record_key": row["record_key"]})
    assert deletion.status_code == 202
    with SessionLocal() as db:
        assert db.get(PrivacyJob, job["id"]).state == "cancelled"
        assert db.get(ExportChunk, (job["id"], 0)) is None


def test_export_source_boundary_excludes_later_saves(client):
    tokens = account(client)
    consent(client, tokens)
    save(client, tokens, "before export")
    job = client.post("/v1/privacy/exports", headers=headers(tokens), json={"grant": grant(client, tokens, "export_create")}).json()
    save(client, tokens, "after export")
    assert drain(job["id"]) == "ready"
    with SessionLocal() as db:
        data = b"".join(db.scalars(select(ExportChunk.payload).where(ExportChunk.job_id == job["id"])))
        assert b"before export" in data and b"after export" not in data


def test_sqlite_concurrent_grant_consumption(client):
    from concurrent.futures import ThreadPoolExecutor
    tokens = account(client)
    credential = grant(client, tokens, "delete_saved")
    def attempt(_):
        return client.post("/v1/privacy/deletions", headers=headers(tokens), json={"scope": "saved", "grant": credential}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, range(2))) == [202, 403]


def test_stream_rechecks_session_between_chunks(client):
    from app.models import User
    from app.privacy_jobs import stream_export
    tokens = account(client)
    consent(client, tokens)
    save(client, tokens)
    job = client.post("/v1/privacy/exports", headers=headers(tokens), json={"grant": grant(client, tokens, "export_create")}).json()
    assert drain(job["id"]) == "ready"
    with SessionLocal() as db:
        user = db.scalar(select(User))
        user_id, lifecycle = user.id, user.lifecycle_id
    stream = stream_export(job["id"], user_id, lifecycle, tokens["session_id"], tokens["access_token"])
    assert next(stream).startswith(b'{"type":"manifest"')
    client.post("/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    import pytest
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        next(stream)


def test_failed_account_purge_never_reopens_account(client):
    tokens = account(client)
    job = client.post("/v1/privacy/deletions", headers=headers(tokens), json={"scope": "account",
        "receipt": "failed-account-receipt-" + "f" * 32, "grant": grant(client, tokens, "delete_account")}).json()
    for _ in range(6):
        with SessionLocal() as db:
            fail_job(db, job["id"])
    assert client.get("/analysis/history", headers=headers(tokens)).status_code == 401
    with SessionLocal() as db:
        row = db.get(PrivacyJob, job["id"])
        assert row.state == "failed"
        new = retry_marker(db, row.marker_id)
    assert drain(new) == "completed"


def test_large_legacy_records_are_staged_as_bounded_stream_chunks(client):
    from app.models import User, Analysis
    from datetime import datetime, timezone
    tokens = account(client)
    with SessionLocal() as db:
        user = db.scalar(select(User))
        for _ in range(2):
            db.add(Analysis(user_id=user.id, lifecycle_id=user.lifecycle_id, generation=0,
                content="synthetic large legacy " * 35000, score=0, verdict="low-risk",
                created_at=datetime.fromtimestamp(int(time.time()), timezone.utc).replace(tzinfo=None),
                expires_at=int(time.time()) + seconds(90), provenance="legacy_no_retroactive_consent"))
        db.commit()
    job = client.post("/v1/privacy/exports", headers=headers(tokens), json={"grant": grant(client, tokens, "export_create")}).json()
    assert drain(job["id"]) == "ready"
    with SessionLocal() as db:
        chunks = list(db.scalars(select(ExportChunk).where(ExportChunk.job_id == job["id"])))
        assert sum(len(chunk.payload) for chunk in chunks) > 1000000
        assert all(len(chunk.payload) <= policy.export_max_bytes // policy.batch_size for chunk in chunks)
