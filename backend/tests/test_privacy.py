import json
import time
from uuid import uuid4
from sqlalchemy import select, func
from app.database import SessionLocal
from app.models import Analysis
from app.privacy_models import ConsentReceipt, AuditEvent
from app.privacy_config import policy, seconds
from tests.privacy_helpers import account, headers, consent, save, grant, drain


def test_transient_default_and_strict_server_fields(client):
    tokens = account(client)
    response = client.post("/analysis/analyze", headers=headers(tokens), json={"content": "urgent message"})
    assert set(response.json()) == {"score", "verdict", "flags"}
    assert client.get("/analysis/history", headers=headers(tokens)).json()["total"] == 0
    for field in ("owner", "lifecycle_id", "expires_at", "deleted_at", "authorization"):
        assert client.post("/analysis/analyze", headers=headers(tokens), json={"content": "hello", field: "forged"}).status_code == 422
        assert client.post("/v1/privacy/analyses", headers=headers(tokens), json={"content": "hello", "save": True, field: "forged"}).status_code == 422


def test_saving_requires_explicit_choice_and_current_consent(client):
    tokens = account(client)
    assert save(client, tokens).status_code == 403
    assert consent(client, tokens).status_code == 200
    assert client.post("/v1/privacy/analyses", headers=headers(tokens), json={"content": "hello", "save": False}).status_code == 422
    key = str(uuid4())
    first = save(client, tokens, "private synthetic", key)
    second = save(client, tokens, "private synthetic", key)
    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()
    assert first.json()["expires_at"] == int(time.time()) + seconds(90)
    assert save(client, tokens, "different", key).status_code == 409
    assert consent(client, tokens, False).status_code == 200
    assert save(client, tokens).status_code == 403
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Analysis)) == 1
        assert all(row.expires_at - row.created_at == seconds(730) for row in db.scalars(select(ConsentReceipt)))


def test_two_user_isolation_all_private_paths(client):
    a, b = account(client), account(client, "other@example.com")
    consent(client, a)
    saved = save(client, a, "unique synthetic sentinel").json()
    for url in ("/analysis/history", "/analysis/history?search=sentinel"):
        result = client.get(url, headers=headers(b)).json()
        assert result["total"] == 0 and result["items"] == []
    assert client.get(f"/v1/privacy/analyses/{saved['id']}", headers=headers(b)).status_code == 404
    assert client.request("DELETE", f"/v1/privacy/analyses/{saved['id']}", headers=headers(b), json={"record_key": saved["record_key"]}).status_code == 404
    job = client.post("/v1/privacy/exports", headers=headers(a), json={"grant": grant(client, a, "export_create")}).json()
    assert client.get(f"/v1/privacy/exports/{job['id']}", headers=headers(b)).status_code == 404
    assert client.get(f"/v1/privacy/exports/{job['id']}/content", headers={**headers(b), "X-Recent-Auth": "invalid"}).status_code == 404


def test_jsonl_export_exclusions_and_separate_grants(client):
    tokens = account(client)
    consent(client, tokens)
    save(client, tokens, "synthetic export text")
    creation = grant(client, tokens, "export_create")
    job = client.post("/v1/privacy/exports", headers=headers(tokens), json={"grant": creation}).json()
    assert drain(job["id"]) == "ready"
    url = f"/v1/privacy/exports/{job['id']}/content"
    assert client.get(url, headers={**headers(tokens), "X-Recent-Auth": creation}).status_code == 403
    download = grant(client, tokens, "export_download", job["id"])
    response = client.get(url, headers={**headers(tokens), "X-Recent-Auth": download})
    assert response.status_code == 200
    rows = [json.loads(line) for line in response.content.splitlines()]
    assert rows[0]["format_version"] == 1 and rows[-1]["complete"] is True
    assert any(row.get("content") == "synthetic export text" for row in rows)
    for forbidden in ("password", "password_hash", "access_token", "refresh_token", "digest", "notice_hash"):
        assert all(forbidden not in row for row in rows)
    assert client.get(url, headers={**headers(tokens), "X-Recent-Auth": download}).status_code == 403


def test_validation_cache_and_audit_redaction(client):
    tokens = account(client)
    secret = "raw-input-secret-sentinel"
    response = client.post("/v1/privacy/reauthenticate", headers=headers(tokens), json={"password": secret, "action": "bad", "target": "self"})
    assert response.status_code == 422 and secret not in response.text
    assert response.headers["cache-control"] == "no-store"
    consent(client, tokens)
    save(client, tokens, secret)
    with SessionLocal() as db:
        rows = list(db.scalars(select(AuditEvent)))
        assert all(secret not in repr(row.__dict__) and "privacy@example.com" not in repr(row.__dict__) for row in rows)
        assert all(row.expires_at - row.created_at == seconds(365) for row in rows)


def test_private_access_log_redaction():
    import logging
    from app.privacy_logging import PrivateAccessFilter
    record = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1", "GET", "/analysis/history?search=private-secret-sentinel", "1.1", 200), None)
    assert PrivateAccessFilter().filter(record)
    assert "private-secret-sentinel" not in record.getMessage()
