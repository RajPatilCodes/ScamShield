import os
import tempfile
from pathlib import Path

_TEST_DB_DIR = tempfile.TemporaryDirectory(prefix="scamshield-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{(Path(_TEST_DB_DIR.name) / 'test.db').as_posix()}"
os.environ["JWT_SECRET"] = "test-secret"

import pytest
from fastapi.testclient import TestClient
from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    return TestClient(app)
