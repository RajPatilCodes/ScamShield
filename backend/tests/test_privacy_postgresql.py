"""Opt-in disposable PostgreSQL tests; no Compose/customer database access."""
import os
import time
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from sqlalchemy import create_engine, text, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from alembic import command
from alembic.config import Config
from app.database import Base
from app.models import User, Analysis
from app.privacy_models import PrivacyJob
from app.privacy_jobs import process_job
from app.privacy_rate_limits import check
from app.main import app
from app.database import get_db
from fastapi.testclient import TestClient
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from tests.privacy_helpers import account, headers, grant, consent, save, PASSWORD


@pytest.fixture
def postgres(tmp_path, monkeypatch):
    url = os.environ.get("PRIVACY_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("No explicitly disposable PostgreSQL test service configured")
    parsed = make_url(url)
    if (url != os.environ.get("PRIVACY_TEST_POSTGRES_CONFIRM") or parsed.drivername != "postgresql+psycopg"
        or not parsed.database or not parsed.database.startswith("phase3_test_") or parsed.host not in ("localhost", "127.0.0.1", "::1")):
        pytest.fail("Refusing non-disposable PostgreSQL target")
    schema = "phase3_" + uuid4().hex
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    with engine.begin() as db:
        db.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        migration_url = parsed.update_query_dict({"options": f"-csearch_path={schema}"}).render_as_string(hide_password=False)
        config.attributes.update(database_url=migration_url, migration_target=migration_url)
        command.upgrade(config, "head")
        factory = sessionmaker(bind=engine)
        from app.privacy_config import policy
        from app.ownership import initialise_authority
        monkeypatch.setattr(policy, "authority_path", str(tmp_path / "postgres-authority.db"))
        with factory() as db:
            initialise_authority(db)
        yield engine, factory
    finally:
        with engine.begin() as db:
            db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


@pytest.fixture
def pg_client(postgres):
    _, factory = postgres
    def database():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = database
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_postgres_migration_metadata_and_integrity(postgres):
    engine, _ = postgres
    with engine.connect() as db:
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == "0003"
        assert compare_metadata(MigrationContext.configure(db), Base.metadata) == []


def test_postgres_concurrent_privacy_rate_limit(postgres):
    engine, factory = postgres
    lifecycle = str(uuid4())
    def attempt(_):
        with factory() as db:
            try:
                check(db, "synthetic", lifecycle, "127.0.0.1", 3)
                db.commit()
                return True
            except Exception:
                db.rollback()
                return False
    with ThreadPoolExecutor(max_workers=5) as pool:
        assert sum(pool.map(attempt, range(5))) == 3


def test_postgres_lifecycle_job_recheck(postgres):
    engine, factory = postgres
    with factory() as db:
        user = User(email="synthetic@example.com", password_hash="synthetic", email_verified=True)
        db.add(user)
        db.flush()
        job = PrivacyJob(user_id=user.id, lifecycle_id=user.lifecycle_id, revision=0, generation=0,
            kind="export", created_at=1, next_attempt_at=1, staging_expires_at=int(time.time()) + 86400)
        db.add(job)
        db.flush()
        job_id = job.id
        user.privacy_revision = 1
        db.commit()
    assert process_job(job_id, factory)
    with factory() as db:
        assert db.get(PrivacyJob, job_id).state == "cancelled"


def test_postgres_grant_concurrent_consumption(pg_client):
    tokens = account(pg_client)
    credential = grant(pg_client, tokens, "delete_saved")
    def attempt(_):
        return pg_client.post("/v1/privacy/deletions", headers=headers(tokens),
            json={"scope": "saved", "grant": credential}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, range(2))) == [202, 403]


def test_postgres_recovery_account_deletion_race(pg_client):
    from app.email_delivery import captures
    tokens = account(pg_client)
    credential = grant(pg_client, tokens, "delete_account")
    pg_client.post("/v1/auth/recovery/request", json={"email": "privacy@example.com"})
    challenge = captures[-1].token
    def attempt(kind):
        if kind == "recovery":
            return pg_client.post("/v1/auth/recovery/confirm", json={"token": challenge, "password": PASSWORD + "-changed"}).status_code
        return pg_client.post("/v1/privacy/deletions", headers=headers(tokens), json={
            "scope": "account", "grant": credential, "receipt": "postgres-status-receipt-" + "z" * 32}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        recovery, deletion = list(pool.map(attempt, ["recovery", "deletion"]))
    assert (recovery == 204 and deletion in (401, 403)) or (recovery == 400 and deletion == 202)


def test_postgres_global_export_slots(postgres):
    engine, factory = postgres
    from app.privacy_rate_limits import private_digest
    with factory() as lock_db:
        for index in range(2):
            key = int.from_bytes(bytes.fromhex(private_digest(f"export-slot-{index}"))[:8], "big", signed=True)
            lock_db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
        with factory() as db:
            user = User(email="slots@example.com", password_hash="synthetic", email_verified=True)
            db.add(user)
            db.flush()
            job = PrivacyJob(user_id=user.id, lifecycle_id=user.lifecycle_id, revision=0, generation=0,
                kind="export", created_at=int(time.time()), next_attempt_at=1, staging_expires_at=int(time.time()) + 86400)
            db.add(job)
            db.flush()
            job_id = job.id
            db.commit()
        assert process_job(job_id, factory) is False
        lock_db.rollback()
    assert process_job(job_id, factory) is True


def test_postgres_post_lock_retry_deadline_recheck(pg_client, postgres, monkeypatch):
    from threading import Event
    import app.privacy_jobs as jobs
    _, factory = postgres
    tokens = account(pg_client)
    job = pg_client.post("/v1/privacy/exports", headers=headers(tokens),
        json={"grant": grant(pg_client, tokens, "export_create")}).json()
    observed, release = Event(), Event()
    lock = jobs.locked_owner
    def wait_for_postponement(db, *args):
        observed.set()
        assert release.wait(10)
        return lock(db, *args)
    monkeypatch.setattr(jobs, "locked_owner", wait_for_postponement)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(process_job, job["id"], factory)
        try:
            assert observed.wait(10)
            with factory() as db:
                jobs.fail_job(db, job["id"])
        finally:
            release.set()
        assert future.result(timeout=10) is False
    with factory() as db:
        row = db.get(PrivacyJob, job["id"])
        assert row.phase == "start" and row.total_bytes == 0 and row.retry_count == 1
        assert row.next_attempt_at > int(time.time())
