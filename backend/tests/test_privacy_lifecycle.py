import time
from sqlalchemy import select, func, update
from app.database import SessionLocal
from app.models import Analysis, User, AuthSession
from app.privacy_models import DeletionMarker, PrivacyJob, ExportChunk
from app.privacy_jobs import sweep
from tests.privacy_helpers import account, headers, consent, save, grant, drain
import pytest
from app.ownership import AuthorityUnavailable, reconcile_authority
from app.privacy_config import policy
from app.privacy_models import FenceCheckpoint


def test_missing_authority_blocks_activation_and_processing(client, monkeypatch, tmp_path):
    from app.privacy_jobs import process_job
    tokens = account(client)
    job = client.post("/v1/privacy/exports", headers=headers(tokens),
                      json={"grant": grant(client, tokens, "export_create")}).json()
    missing = tmp_path / "missing.db"
    monkeypatch.setattr(policy, "authority_path", str(missing))
    assert client.get("/analysis/history", headers=headers(tokens)).status_code == 503
    assert client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 503
    assert client.post("/v1/auth/register", json={"email": "another@example.com", "password": "password123"}).status_code == 503
    with pytest.raises(AuthorityUnavailable):
        process_job(job["id"])
    assert not missing.exists()
    with SessionLocal() as db:
        assert db.get(PrivacyJob, job["id"]).retry_count == 0


def test_stale_empty_authority_is_not_accepted_as_current(client, monkeypatch, tmp_path):
    import shutil
    tokens = account(client)
    stale = tmp_path / "stale-authority.db"
    shutil.copyfile(policy.authority_path, stale)
    assert client.post("/v1/privacy/deletions", headers=headers(tokens),
        json={"scope": "saved", "grant": grant(client, tokens, "delete_saved")}).status_code == 202
    monkeypatch.setattr(policy, "authority_path", str(stale))
    assert client.get("/analysis/history", headers=headers(tokens)).status_code == 503
    with SessionLocal() as db, pytest.raises(AuthorityUnavailable):
        reconcile_authority(db)


def test_restored_database_without_newer_markers_is_quarantined_then_fenced(client):
    tokens = account(client)
    consent(client, tokens)
    saved = save(client, tokens).json()
    with SessionLocal() as db:
        checkpoint = db.get(FenceCheckpoint, 1)
        original = (checkpoint.revision, checkpoint.digest)
    job = client.post("/v1/privacy/deletions", headers=headers(tokens),
        json={"scope": "saved", "grant": grant(client, tokens, "delete_saved")}).json()
    # Reproduce an older backup: old generation, old checkpoint, no newer ledger.
    with SessionLocal() as db:
        db.execute(DeletionMarker.__table__.delete())
        checkpoint = db.get(FenceCheckpoint, 1)
        checkpoint.revision, checkpoint.digest = original
        db.execute(update(User).values(data_generation=0, privacy_revision=0))
        db.commit()
    assert client.get("/analysis/history", headers=headers(tokens)).status_code == 503
    with SessionLocal() as db:
        reconcile_authority(db)
    assert client.get("/analysis/history", headers=headers(tokens)).json()["total"] == 0
    assert client.get(f"/v1/privacy/analyses/{saved['id']}", headers=headers(tokens)).status_code == 404
    assert drain(job["id"]) == "completed"


def test_interrupted_authority_first_commit_stays_closed_and_reconciles(client):
    from app.ownership import publish_marker
    tokens = account(client)
    with SessionLocal() as db:
        user = db.scalar(select(User))
        marker = DeletionMarker(user_id=user.id, lifecycle_id=user.lifecycle_id, scope="account",
            generation=0, revision=1, created_at=int(time.time()))
        db.add(marker)
        publish_marker(db, marker)
        db.rollback()  # Crash between authority commit and local commit.
    assert client.get("/analysis/history", headers=headers(tokens)).status_code == 503
    with SessionLocal() as db:
        reconcile_authority(db)
    assert client.get("/analysis/history", headers=headers(tokens)).status_code == 401


def test_original_record_key_cannot_delete_replacement_with_reused_integer_id(client):
    tokens = account(client)
    consent(client, tokens)
    old = save(client, tokens, "old saved content").json()
    deletion = client.request("DELETE", f"/v1/privacy/analyses/{old['id']}", headers=headers(tokens),
        json={"record_key": old["record_key"]}).json()
    assert drain(deletion["id"]) == "completed"
    fresh = save(client, tokens, "replacement saved content").json()
    assert fresh["id"] == old["id"] and fresh["record_key"] != old["record_key"]
    assert client.request("DELETE", f"/v1/privacy/analyses/{old['id']}", headers=headers(tokens),
        json={"record_key": old["record_key"]}).status_code == 404
    assert client.get(f"/v1/privacy/analyses/{fresh['id']}", headers=headers(tokens)).json()["content"] == fresh["content"]


def test_reconciliation_reopens_satisfied_intent_for_reintroduced_data(client):
    from app.privacy_jobs import retry_marker
    tokens = account(client)
    consent(client, tokens)
    saved = save(client, tokens).json()
    with SessionLocal() as db:
        row = db.get(Analysis, saved["id"])
        original = {column.name: getattr(row, column.name) for column in Analysis.__table__.columns}
    job = client.post("/v1/privacy/deletions", headers=headers(tokens),
        json={"scope": "saved", "grant": grant(client, tokens, "delete_saved")}).json()
    assert drain(job["id"]) == "completed"
    with SessionLocal() as db:
        db.add(Analysis(**original))  # Synthetic reintroduction of pre-purge data.
        db.commit()
        reconcile_authority(db)
        marker = db.scalar(select(DeletionMarker))
        assert marker.satisfied_at is None
        retry = retry_marker(db, marker.id)
    assert client.get("/analysis/history", headers=headers(tokens)).json()["total"] == 0
    assert drain(retry) == "completed"
    with SessionLocal() as db:
        assert db.get(Analysis, saved["id"]) is None


def test_individual_delete_immediate_retryable_and_no_reauth(client):
    tokens = account(client)
    consent(client, tokens)
    row = save(client, tokens).json()
    response = client.request("DELETE", f"/v1/privacy/analyses/{row['id']}", headers=headers(tokens), json={"record_key": row["record_key"]})
    assert response.status_code == 202
    assert client.get("/analysis/history", headers=headers(tokens)).json()["total"] == 0
    assert client.get(f"/v1/privacy/analyses/{row['id']}", headers=headers(tokens)).status_code == 404
    assert drain(response.json()["id"]) == "completed"
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Analysis)) == 0


def test_bulk_delete_fences_old_work_but_new_explicit_save_survives(client):
    tokens = account(client)
    consent(client, tokens)
    old = save(client, tokens).json()
    assert client.post("/v1/privacy/deletions", headers=headers(tokens), json={"scope": "saved", "grant": "invalid"}).status_code == 403
    job = client.post("/v1/privacy/deletions", headers=headers(tokens), json={"scope": "saved", "grant": grant(client, tokens, "delete_saved")}).json()
    assert client.get("/analysis/history", headers=headers(tokens)).json()["total"] == 0
    fresh = save(client, tokens, "new explicit saved data").json()
    assert drain(job["id"]) == "completed"
    items = client.get("/analysis/history", headers=headers(tokens)).json()["items"]
    assert len(items) == 1 and items[0]["id"] == fresh["id"]
    with SessionLocal() as db:
        assert db.scalar(select(Analysis).where(Analysis.record_key == old["record_key"])) is None


def test_account_delete_receipt_and_new_lifecycle(client):
    tokens = account(client)
    consent(client, tokens)
    save(client, tokens)
    with SessionLocal() as db:
        life = db.scalar(select(User.lifecycle_id))
    receipt = "synthetic-status-receipt-" + "x" * 32
    job = client.post("/v1/privacy/deletions", headers=headers(tokens), json={
        "scope": "account", "receipt": receipt, "grant": grant(client, tokens, "delete_account")})
    assert job.status_code == 202
    assert client.get("/analysis/history", headers=headers(tokens)).status_code == 401
    assert client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401
    assert client.post("/v1/privacy/deletions/status", json={"receipt": receipt}).json()["state"] == "queued"
    assert drain(job.json()["id"]) == "completed"
    new = account(client)
    with SessionLocal() as db:
        assert db.scalar(select(User.lifecycle_id)) != life
        assert db.scalar(select(func.count()).select_from(Analysis)) == 0
    assert client.get("/analysis/history", headers=headers(new)).json()["total"] == 0


def test_expiry_excludes_detail_search_count_and_purge(client):
    tokens = account(client)
    consent(client, tokens)
    row = save(client, tokens, "expiry sentinel").json()
    with SessionLocal() as db:
        db.get(Analysis, row["id"]).expires_at = int(time.time())
        db.commit()
    assert client.get("/analysis/history?search=sentinel", headers=headers(tokens)).json()["total"] == 0
    assert client.get(f"/v1/privacy/analyses/{row['id']}", headers=headers(tokens)).status_code == 404
    with SessionLocal() as db:
        sweep(db)
        assert db.get(Analysis, row["id"]) is None


def test_imported_marker_fences_restored_account(client):
    tokens = account(client)
    receipt = "restored-status-receipt-" + "y" * 32
    response = client.post("/v1/privacy/deletions", headers=headers(tokens), json={
        "scope": "account", "receipt": receipt, "grant": grant(client, tokens, "delete_account")})
    assert response.status_code == 202
    # Synthetic older account/session rows restored without discarding newer markers.
    with SessionLocal() as db:
        db.execute(update(User).values(is_active=True, privacy_state="active", privacy_revision=0))
        db.execute(update(AuthSession).values(revoked_at=None))
        db.commit()
    assert client.get("/analysis/history", headers=headers(tokens)).status_code == 401
