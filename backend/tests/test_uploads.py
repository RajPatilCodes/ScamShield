import hashlib

import pytest

from app.routes import uploads
from tests.test_api import register


def upload(client, filename="photo.png", content=b"example bytes", content_type="image/png"):
    token = register(client)
    return client.post("/analysis/upload", headers={"Authorization": f"Bearer {token}"},
                       files={"file": (filename, content, content_type)})


def test_upload_requires_auth(client):
    assert client.post("/analysis/upload", files={"file": ("photo.png", b"data", "image/png")}).status_code == 401


@pytest.mark.parametrize("filename,content_type", [("photo.png", "image/png"), ("clip.mp4", "video/mp4")])
def test_upload_hash_and_metadata(client, filename, content_type):
    response = upload(client, filename=filename, content_type=content_type)
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == filename
    assert data["content_type"] == content_type
    assert data["size"] == len(b"example bytes")
    assert data["hash"] == hashlib.sha256(b"example bytes").hexdigest()
    assert data["risk"] == 0
    assert data["verdict"] == "unverified"
    assert "not scanned" in data["flags"][0]
    assert data["actions"]


def test_upload_flags_disguised_executable(client):
    response = upload(client, filename="photo.png.exe")
    assert response.json()["risk"] == 100
    assert response.json()["verdict"] == "high-risk"


def test_upload_rejects_unsupported_type(client):
    assert upload(client, content_type="application/octet-stream").status_code == 415


def test_upload_rejects_empty_file(client):
    assert upload(client, content=b"").status_code == 422


def test_upload_enforces_size_limit(client, monkeypatch):
    monkeypatch.setattr(uploads, "MAX_UPLOAD_BYTES", 4)
    assert upload(client, content=b"12345").status_code == 413


def test_upload_accepts_exact_size_limit(client, monkeypatch):
    monkeypatch.setattr(uploads, "MAX_UPLOAD_BYTES", 4)
    assert upload(client, content=b"1234").status_code == 200
