import asyncio
import hashlib

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.routes import media
from tests.test_api import register

PNG = b"\x89PNG\r\n\x1a\n" + b"example"
MP4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00"


def upload(client, filename="photo.png", content=PNG, content_type="image/png"):
    token = register(client)
    return client.post("/analysis/media", headers={"Authorization": f"Bearer {token}"},
                       files={"file": (filename, content, content_type)})


def test_requires_auth(client):
    assert client.post("/analysis/media", content=b"invalid").status_code == 401


@pytest.mark.parametrize("filename,content,content_type", [
    ("photo.png", PNG, "image/png"), ("clip.mp4", MP4, "video/mp4"),
])
def test_response_contract(client, filename, content, content_type):
    response = upload(client, filename, content, content_type)
    assert response.status_code == 200
    result = response.json()
    assert set(result) == {"filename", "content_type", "size_bytes", "sha256", "verdict", "flags", "actions", "malware_scanned"}
    assert result["filename"] == filename
    assert result["content_type"] == content_type
    assert result["size_bytes"] == len(content)
    assert result["sha256"] == hashlib.sha256(content).hexdigest()
    assert result["verdict"] == "unverified"
    assert result["malware_scanned"] is False
    assert "cannot establish malware-free status" in result["flags"][0]
    assert result["actions"]


@pytest.mark.parametrize("filename,content,content_type,status", [
    ("photo.exe", PNG, "image/png", 415),
    ("photo.png", PNG, "video/mp4", 415),
    ("photo.png", PNG, "application/octet-stream", 415),
    ("photo.png", b"MZexecutable", "image/png", 415),
    ("photo.png", b"", "image/png", 422),
])
def test_rejections(client, filename, content, content_type, status):
    assert upload(client, filename, content, content_type).status_code == status


def test_risky_name_and_basename(client):
    result = upload(client, "../../photo.exe.png").json()
    assert result["filename"] == "photo.exe.png"
    assert result["verdict"] == "review"


@pytest.mark.parametrize("extra,status", [(0, 200), (1, 413)])
def test_real_size_boundary(client, extra, status):
    content = PNG + b"x" * (20 * 1024 * 1024 - len(PNG) + extra)
    assert upload(client, content=content).status_code == status


def test_multiple_files_rejected(client):
    token = register(client)
    response = client.post("/analysis/media", headers={"Authorization": f"Bearer {token}"},
                           files=[("file", ("a.png", PNG, "image/png")), ("file", ("b.png", PNG, "image/png"))])
    assert response.status_code == 422


def multipart(content=PNG, closing=True):
    body = b'--test\r\nContent-Disposition: form-data; name="file"; filename="a.png"\r\nContent-Type: image/png\r\n\r\n' + content
    return body + (b"\r\n--test--\r\n" if closing else b"")


def streamed_request(chunks):
    iterator = iter(chunks)

    async def receive():
        chunk = next(iterator, None)
        return {"type": "http.request", "body": chunk or b"", "more_body": chunk is not None}

    return Request({"type": "http", "headers": [(b"content-type", b"multipart/form-data; boundary=test")]}, receive)


def test_fragmented_stream():
    body = multipart()
    result = asyncio.run(media.screen_media(streamed_request([bytes([byte]) for byte in body]), user=None))
    assert result.sha256 == hashlib.sha256(PNG).hexdigest()


def test_incomplete_stream():
    with pytest.raises(HTTPException) as error:
        asyncio.run(media.screen_media(streamed_request([multipart(closing=False)]), user=None))
    assert error.value.status_code == 422


def test_stream_stops_at_limit(monkeypatch):
    monkeypatch.setattr(media, "MAX_MEDIA_BYTES", len(PNG))

    def chunks():
        yield multipart(PNG + b"x", closing=False) + b"\r\n"
        raise AssertionError("Request read beyond the file limit")

    with pytest.raises(HTTPException) as error:
        asyncio.run(media.screen_media(streamed_request(chunks()), user=None))
    assert error.value.status_code == 413


@pytest.mark.parametrize("content_type,header", [
    ("image/jpeg", b"\xff\xd8\xff"), ("image/gif", b"GIF89a"),
    ("image/bmp", b"BM"), ("image/tiff", b"II\x2a\x00"),
    ("image/webp", b"RIFF0000WEBP"), ("video/x-msvideo", b"RIFF0000AVI "),
    ("video/webm", b"\x1a\x45\xdf\xa3"), ("video/x-matroska", b"\x1a\x45\xdf\xa3"),
    ("video/mpeg", b"\x00\x00\x01\xba"),
    ("image/avif", b"0000ftypavif0000"), ("video/quicktime", b"0000ftypqt  0000"),
])
def test_basic_signatures(content_type, header):
    assert media.matches_signature(content_type, header)
    assert not media.matches_signature(content_type, b"invalid bytes")
