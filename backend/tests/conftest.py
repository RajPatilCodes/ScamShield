import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

_TEST_DB_DIR = tempfile.TemporaryDirectory(prefix="scamshield-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{(Path(_TEST_DB_DIR.name) / 'test.db').as_posix()}"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["ENVIRONMENT"] = "test"
os.environ["EMAIL_ADAPTER"] = "capture"
os.environ["ARGON2_TIME_COST"] = "1"
os.environ["ARGON2_MEMORY_COST"] = "8192"
os.environ["ARGON2_PARALLELISM"] = "1"
os.environ["VERIFICATION_EXPIRE_MINUTES"] = "30"
os.environ["PUBLIC_API_URL"] = "http://10.0.2.2:8000"

import pytest
import jwt
from fastapi.testclient import TestClient
from app.database import Base, engine, validate_disposable_database
from app.email_delivery import captures
from app.main import app


@pytest.fixture(autouse=True)
def synthetic_clock(monkeypatch):
    # A shared synthetic wall clock avoids WSL/host clock corrections between
    # JWT issuance and verification. Production timing validation is untouched.
    instant = int(time.time())

    class SyntheticDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            value = datetime.fromtimestamp(instant, timezone.utc)
            return value.astimezone(tz) if tz else value.replace(tzinfo=None)

    monkeypatch.setattr(time, "time", lambda: instant)
    monkeypatch.setattr(jwt.api_jwt, "datetime", SyntheticDateTime)


@pytest.fixture(autouse=True)
def reset_db():
    validate_disposable_database(engine, Path(_TEST_DB_DIR.name))
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    captures.clear()
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
