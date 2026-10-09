import time
from sqlalchemy import select
from app.database import SessionLocal
from app.privacy_models import PrivacyRateBucket
from tests.privacy_helpers import account, headers, PASSWORD


def test_failed_reauth_limit_and_success_does_not_reset_it(client):
    tokens = account(client)
    body = {"password": "wrong-password", "action": "export_create", "target": "self"}
    for _ in range(5):
        assert client.post("/v1/privacy/reauthenticate", headers=headers(tokens), json=body).status_code == 403
    body["password"] = PASSWORD
    response = client.post("/v1/privacy/reauthenticate", headers=headers(tokens), json=body)
    assert response.status_code == 429 and int(response.headers["Retry-After"]) == 900
    with SessionLocal() as db:
        db.scalar(select(PrivacyRateBucket)).expires_at = int(time.time())
        db.commit()
    assert client.post("/v1/privacy/reauthenticate", headers=headers(tokens), json=body).status_code == 200


def test_export_read_shared_bucket_and_owner_isolation(client):
    a, b = account(client), account(client, "other-rate@example.com")
    for _ in range(10):
        assert client.get("/v1/privacy/exports", headers=headers(a)).status_code == 200
    assert client.get("/v1/privacy/exports", headers=headers(a)).status_code == 429
    assert client.get("/v1/privacy/exports", headers=headers(b)).status_code == 200


def test_deletion_and_receipt_limits(client):
    from tests.privacy_helpers import grant
    tokens = account(client)
    for _ in range(3):
        assert client.post("/v1/privacy/deletions", headers=headers(tokens), json={"scope": "saved", "grant": "invalid"}).status_code == 403
    assert client.post("/v1/privacy/deletions", headers=headers(tokens), json={"scope": "saved", "grant": "invalid"}).status_code == 429
    for _ in range(10):
        assert client.post("/v1/privacy/deletions/status", json={"receipt": "unknown-receipt-" + "x" * 32}).status_code == 404
    assert client.post("/v1/privacy/deletions/status", json={"receipt": "unknown-receipt-" + "x" * 32}).status_code == 429
