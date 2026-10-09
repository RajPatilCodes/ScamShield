import time
from sqlalchemy import select
from app.database import SessionLocal
from app.privacy_models import RecentAuthGrant
from tests.privacy_helpers import account, headers, grant, PASSWORD
from app.email_delivery import captures


def request_export(client, tokens, credential):
    return client.post("/v1/privacy/exports", headers=headers(tokens), json={"grant": credential})


def test_grant_expiry_target_and_single_use(client):
    tokens = account(client)
    credential = grant(client, tokens, "export_create")
    with SessionLocal() as db:
        row = db.scalar(select(RecentAuthGrant))
        assert row.expires_at == int(time.time()) + 300
        row.expires_at = int(time.time())
        db.commit()
    assert request_export(client, tokens, credential).status_code == 403
    wrong = grant(client, tokens, "delete_saved")
    assert request_export(client, tokens, wrong).status_code == 403


def test_refresh_never_creates_grant_and_other_session_cannot_consume(client):
    tokens = account(client)
    credential = grant(client, tokens, "export_create")
    other = client.post("/v1/auth/login", json={"email": "privacy@example.com", "password": PASSWORD}).json()
    assert request_export(client, other, credential).status_code == 403
    rotated = client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).json()
    assert request_export(client, rotated, "fresh-access-is-not-human-auth").status_code == 403


def test_logout_revoke_and_recovery_invalidate_grants(client):
    for operation in ("logout", "revoke", "recovery"):
        email = f"{operation}@example.com"
        tokens = account(client, email)
        credential = grant(client, tokens, "export_create")
        if operation == "logout":
            assert client.post("/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}).status_code == 204
        elif operation == "revoke":
            assert client.delete(f"/v1/auth/sessions/{tokens['session_id']}", headers=headers(tokens)).status_code == 204
        else:
            client.post("/v1/auth/recovery/request", json={"email": email})
            assert client.post("/v1/auth/recovery/confirm", json={"token": captures[-1].token, "password": PASSWORD}).status_code == 204
        assert request_export(client, tokens, credential).status_code == 401
