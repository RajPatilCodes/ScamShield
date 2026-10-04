import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import jwt
import pytest
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.models import AuthSession, RefreshCredential, User
from tests.test_api import register


def login(client):
    register(client)
    return client.post("/v1/auth/login", json={"email": "user@example.com", "password": "password123"}).json()


def refresh(client, token):
    return client.post("/v1/auth/refresh", json={"refresh_token": token})


def test_rotation_replay_revokes_family(client):
    initial = login(client)
    successor = refresh(client, initial["refresh_token"])
    assert successor.status_code == 200
    body = successor.json()
    assert body["refresh_token"] != initial["refresh_token"] and body["session_id"] == initial["session_id"]
    assert refresh(client, initial["refresh_token"]).status_code == 401
    assert refresh(client, body["refresh_token"]).status_code == 401
    for token in (initial["access_token"], body["access_token"]):
        assert client.get("/analysis/history", headers={"Authorization": f"Bearer {token}"}).status_code == 401


@pytest.mark.parametrize("expiry", ["credential", "idle", "absolute"])
def test_expired_refresh(client, expiry):
    body = login(client)
    with SessionLocal() as db:
        row = db.get(AuthSession, body["session_id"])
        if expiry == "credential":
            db.scalar(select(RefreshCredential).where(RefreshCredential.session_id == row.id)).expires_at = 1
        elif expiry == "idle":
            row.idle_expires_at = 1
        else:
            row.idle_expires_at = row.absolute_expires_at = 1
        db.commit()
    assert refresh(client, body["refresh_token"]).status_code == 401


def test_atomic_refresh_race(client):
    body = login(client)
    barrier = Barrier(2)
    def attempt(_):
        barrier.wait()
        return refresh(client, body["refresh_token"])
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, range(2)))
    assert sorted(result.status_code for result in results) == [200, 401]
    winner = next(result.json() for result in results if result.status_code == 200)
    assert refresh(client, winner["refresh_token"]).status_code == 401
    with SessionLocal() as db:
        assert len(list(db.scalars(select(RefreshCredential).where(RefreshCredential.session_id == body["session_id"])))) == 2


def test_logout_idempotent_and_server_authoritative(client):
    body = login(client)
    for _ in range(2):
        assert client.post("/v1/auth/logout", json={"refresh_token": body["refresh_token"]}).status_code == 204
    assert refresh(client, body["refresh_token"]).status_code == 401
    assert client.get("/analysis/history", headers={"Authorization": f"Bearer {body['access_token']}"}).status_code == 401


def test_owner_scope_and_account_session_mismatch(client):
    body = login(client)
    with SessionLocal() as db:
        other = User(email="other@example.com", password_hash="unused", email_verified=True)
        db.add(other)
        db.commit()
        other_id = other.id
    payload = jwt.decode(body["access_token"], settings.jwt_secret, algorithms=["HS256"], audience=settings.jwt_audience)
    payload["sub"] = str(other_id)
    mismatch = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    assert client.get("/v1/auth/sessions", headers={"Authorization": f"Bearer {mismatch}"}).status_code == 401
    headers = {"Authorization": f"Bearer {body['access_token']}"}
    assert all(row["id"] != "not-owned" for row in client.get("/v1/auth/sessions", headers=headers).json()["items"])
    assert client.delete("/v1/auth/sessions/not-owned", headers=headers).status_code == 404
    assert client.delete(f"/v1/auth/sessions/{body['session_id']}", headers=headers).status_code == 204
    assert refresh(client, body["refresh_token"]).status_code == 401


def test_repeated_unknown_refresh_never_issues_credentials(client):
    for _ in range(10):
        assert refresh(client, "synthetic-invalid").status_code == 401
    with SessionLocal() as db:
        assert list(db.scalars(select(AuthSession))) == []


def test_refresh_idle_extension_cannot_exceed_absolute_lifetime(client):
    body = login(client)
    with SessionLocal() as db:
        row = db.get(AuthSession, body["session_id"])
        row.idle_expires_at = row.absolute_expires_at = int(time.time()) + 3600
        db.commit()
    assert refresh(client, body["refresh_token"]).status_code == 200
    with SessionLocal() as db:
        row = db.get(AuthSession, body["session_id"])
        assert row.idle_expires_at == row.absolute_expires_at


def test_other_owner_cannot_list_or_revoke_session(client):
    first = login(client)
    other_creds = {"email": "other@example.com", "password": "synthetic-password"}
    client.post("/v1/auth/register", json=other_creds)
    from app.email_delivery import captures
    client.post("/v1/auth/verification/confirm", json={"token": captures[-1].token})
    second = client.post("/v1/auth/login", json=other_creds).json()
    headers = {"Authorization": f"Bearer {second['access_token']}"}
    assert first["session_id"] not in {row["id"] for row in client.get("/v1/auth/sessions", headers=headers).json()["items"]}
    assert client.delete(f"/v1/auth/sessions/{first['session_id']}", headers=headers).status_code == 404
    assert refresh(client, first["refresh_token"]).status_code == 200


def test_approved_lifetimes(client):
    body = login(client)
    payload = jwt.decode(body["access_token"], settings.jwt_secret, algorithms=["HS256"], audience=settings.jwt_audience)
    assert payload["exp"] - payload["iat"] == 600
    with SessionLocal() as db:
        row = db.get(AuthSession, body["session_id"])
        assert row.idle_expires_at - row.created_at == 7 * 24 * 3600
        assert row.absolute_expires_at - row.created_at == 30 * 24 * 3600
