import time

import bcrypt
import jwt
import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.config import Settings, settings
from app.database import SessionLocal
from app.email_delivery import captures
from app.models import AuthChallenge, AuthSession, User
from app.security import hash_password, verify_password
from tests.test_api import register

CREDS = {"email": "user@example.com", "password": "password123"}


def session_count():
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(AuthSession))


def test_verification_required_and_single_use(client):
    assert client.post("/v1/auth/register", json=CREDS).status_code == 201
    assert session_count() == 0
    assert client.post("/v1/auth/login", json=CREDS).status_code == 401
    token = captures[-1].token
    assert client.post("/v1/auth/verification/confirm", json={"token": token}).status_code == 204
    assert client.post("/v1/auth/verification/confirm", json={"token": token}).status_code == 400
    assert client.post("/v1/auth/login", json=CREDS).status_code == 200


@pytest.mark.parametrize("body", [{"email": "bad", "password": "password123"},
    {**CREDS, "password": "short"}, {**CREDS, "password": "a" * 1025}, {**CREDS, "role": "admin"}])
def test_invalid_registration_never_creates_sessions(client, body):
    assert client.post("/v1/auth/register", json=body).status_code == 422
    assert session_count() == 0


@pytest.mark.parametrize("changes", [{"password": "incorrect"}, {"email": "unknown@example.com"}])
def test_login_failure(client, changes):
    register(client)
    before = session_count()
    assert client.post("/v1/auth/login", json={**CREDS, **changes}).status_code == 401
    assert session_count() == before


def test_disabled_account(client):
    access = register(client)
    with SessionLocal() as db:
        db.scalar(select(User)).is_active = False
        db.commit()
    assert client.post("/v1/auth/login", json=CREDS).status_code == 401
    assert client.get("/analysis/history", headers={"Authorization": f"Bearer {access}"}).status_code == 401
    assert session_count() == 1


@pytest.mark.parametrize("password", ["normal-password", "a" * 1024, "😀" * 1024])
def test_long_password_end_to_end(client, password):
    creds = {**CREDS, "password": password}
    assert client.post("/v1/auth/register", json=creds).status_code == 201
    assert client.post("/v1/auth/verification/confirm", json={"token": captures[-1].token}).status_code == 204
    assert client.post("/v1/auth/login", json=creds).status_code == 200
    with SessionLocal() as db:
        hashed = db.scalar(select(User)).password_hash
    assert hashed.startswith("$argon2id$")
    assert verify_password(password, hashed)
    assert not verify_password(password[:-1] + "x", hashed)


def test_legacy_migration_and_no_truncation(client):
    with SessionLocal() as db:
        db.add(User(email=CREDS["email"], password_hash=bcrypt.hashpw(CREDS["password"].encode(), bcrypt.gensalt()).decode(), email_verified=True))
        db.commit()
    assert client.post("/v1/auth/login", json=CREDS).status_code == 200
    with SessionLocal() as db:
        assert db.scalar(select(User)).password_hash.startswith("$argon2id$")
    legacy = bcrypt.hashpw(b"a" * 72, bcrypt.gensalt()).decode()
    assert not verify_password("a" * 73, legacy)
    assert not verify_password("invalid", "not-a-hash")


def test_recovery_generic_single_use_and_revocation(client):
    access = register(client)
    known = client.post("/v1/auth/recovery/request", json={"email": CREDS["email"]})
    unknown = client.post("/v1/auth/recovery/request", json={"email": "unknown@example.com"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    token = captures[-1].token
    for invalid in ("invalid", captures[0].token):
        assert client.post("/v1/auth/recovery/confirm", json={"token": invalid, "password": "replacement-password"}).status_code == 400
    assert client.post("/v1/auth/recovery/confirm", json={"token": token, "password": "replacement-password"}).status_code == 204
    assert client.post("/v1/auth/recovery/confirm", json={"token": token, "password": "another-password"}).status_code == 400
    assert client.get("/analysis/history", headers={"Authorization": f"Bearer {access}"}).status_code == 401
    assert client.post("/v1/auth/login", json=CREDS).status_code == 401
    assert client.post("/v1/auth/login", json={**CREDS, "password": "replacement-password"}).status_code == 200


@pytest.mark.parametrize("purpose", ["verification", "recovery"])
def test_expired_challenge(client, purpose):
    client.post("/v1/auth/register", json=CREDS)
    if purpose == "recovery":
        client.post("/v1/auth/recovery/request", json={"email": CREDS["email"]})
    token = captures[-1].token
    with SessionLocal() as db:
        challenge = db.scalar(select(AuthChallenge).where(AuthChallenge.purpose == purpose))
        challenge.expires_at = int(time.time()) - 1
        db.commit()
    body = {"token": token}
    if purpose == "recovery":
        body["password"] = "replacement-password"
    assert client.post(f"/v1/auth/{purpose}/confirm", json=body).status_code == 400


def test_login_and_recovery_limits(client):
    for _ in range(5):
        assert client.post("/v1/auth/login", json=CREDS).status_code == 401
    limited = client.post("/v1/auth/login", json=CREDS)
    assert limited.status_code == 429 and int(limited.headers["Retry-After"]) > 0
    assert client.post("/v1/auth/login", json=CREDS, headers={"X-Forwarded-For": "192.0.2.123"}).status_code == 429
    for _ in range(3):
        assert client.post("/v1/auth/recovery/request", json={"email": CREDS["email"]}).status_code == 202
    assert client.post("/v1/auth/recovery/request", json={"email": CREDS["email"]}).status_code == 429
    assert session_count() == 0


@pytest.mark.parametrize("claim", ["sub", "sid", "jti", "iat", "nbf", "exp", "iss", "aud", "purpose"])
def test_missing_claim(client, claim):
    token = register(client)
    payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], audience=settings.jwt_audience)
    del payload[claim]
    bad = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    assert client.get("/analysis/history", headers={"Authorization": f"Bearer {bad}"}).status_code == 401


@pytest.mark.parametrize("changes", [{"exp": 1}, {"purpose": "refresh"}, {"iss": "wrong"}, {"aud": "wrong"},
    {"sub": "999"}, {"iat": True}, {"nbf": int(time.time()) + 3600}, {"sid": "wrong"}])
def test_invalid_token_claims(client, changes):
    token = register(client)
    payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], audience=settings.jwt_audience)
    payload.update(changes)
    bad = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    assert client.get("/analysis/history", headers={"Authorization": f"Bearer {bad}"}).status_code == 401
    assert client.get("/analysis/history", headers={"Authorization": "Bearer malformed"}).status_code == 401


def production(**changes):
    values = dict(environment="production", jwt_secret="a7e1d402cb946f58a79c34ba2396e728", database_url="postgresql+psycopg://synthetic:synthetic@db.invalid/synthetic?sslmode=verify-full",
        public_api_url="https://api.invalid", cors_origins="https://app.invalid", email_adapter="smtp", smtp_host="mail.invalid",
        smtp_username="synthetic", smtp_password="synthetic", smtp_timeout_seconds=1, email_sender="test@example.com", _env_file=None)
    values.update(changes)
    return Settings(**values)


@pytest.mark.parametrize("changes", [{"jwt_secret": ""}, {"jwt_secret": "change-me-in-production"},
    {"jwt_secret": "test-secret"}, {"database_url": "not-a-url"}, {"database_url": "sqlite:///synthetic.db"},
    {"public_api_url": "http://api.invalid"}, {"cors_origins": "*"}, {"email_adapter": "capture"}, {"smtp_host": None},
    {"jwt_secret": "x" * 64}, {"database_url": "postgresql+psycopg://synthetic:synthetic@db.invalid/synthetic?sslmode=disable"}])
def test_unsafe_production_config(changes):
    with pytest.raises((ValueError, ValidationError)):
        production(**changes)


def test_safe_synthetic_config_only():
    assert production().environment == "production"


def test_missing_secret_and_explicit_security_inputs(monkeypatch):
    for variable in ("JWT_SECRET", "ARGON2_TIME_COST", "VERIFICATION_EXPIRE_MINUTES"):
        with monkeypatch.context() as patch:
            patch.delenv(variable)
            with pytest.raises(ValidationError):
                Settings(_env_file=None)


def test_delivery_failure_creates_no_account_or_session(client, monkeypatch):
    from fastapi import HTTPException
    from app import recovery
    def unavailable(*_):
        raise HTTPException(status_code=503, detail="Email delivery unavailable")
    monkeypatch.setattr(recovery, "deliver_challenge", unavailable)
    assert client.post("/v1/auth/register", json=CREDS).status_code == 503
    assert session_count() == 0
    with SessionLocal() as db:
        assert list(db.scalars(select(User))) == []


def test_limits_expire_and_success_cannot_bypass_lockout(client):
    from app.models import AuthRateBucket
    register(client)
    for _ in range(5):
        assert client.post("/v1/auth/login", json={**CREDS, "password": "wrong-password"}).status_code == 401
    assert client.post("/v1/auth/login", json=CREDS).status_code == 429
    with SessionLocal() as db:
        db.scalar(select(AuthRateBucket)).expires_at = 1
        db.commit()
    response = client.post("/v1/auth/login", json=CREDS)
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"


def test_atomic_recovery_race(client):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    register(client)
    client.post("/v1/auth/recovery/request", json={"email": CREDS["email"]})
    challenge = captures[-1].token
    barrier = Barrier(2)
    def attempt(_):
        barrier.wait()
        return client.post("/v1/auth/recovery/confirm", json={"token": challenge, "password": "replacement-password"}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, range(2))) == [204, 400]


def test_recovery_delivery_outage_does_not_enumerate(client, monkeypatch):
    from fastapi import HTTPException
    from app import recovery
    register(client)
    def unavailable(*_):
        raise HTTPException(status_code=503, detail="Email delivery unavailable")
    monkeypatch.setattr(recovery, "deliver_challenge", unavailable)
    known = client.post("/v1/auth/recovery/request", json={"email": CREDS["email"]})
    unknown = client.post("/v1/auth/recovery/request", json={"email": "unknown@example.com"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    with SessionLocal() as db:
        assert list(db.scalars(select(AuthChallenge).where(AuthChallenge.purpose == "recovery"))) == []


def test_wrong_purpose_challenge_rejected(client):
    client.post("/v1/auth/register", json=CREDS)
    client.post("/v1/auth/recovery/request", json={"email": CREDS["email"]})
    token = captures[-1].token
    assert client.post("/v1/auth/verification/confirm", json={"token": token}).status_code == 400
    assert session_count() == 0


def test_argon2_configuration_cannot_silently_downgrade_existing_hash(client):
    from argon2 import PasswordHasher, Type
    stronger = PasswordHasher(type=Type.ID, time_cost=2, memory_cost=16384, parallelism=1).hash(CREDS["password"])
    with SessionLocal() as db:
        db.add(User(email=CREDS["email"], password_hash=stronger, email_verified=True))
        db.commit()
    assert client.post("/v1/auth/login", json=CREDS).status_code == 200
    with SessionLocal() as db:
        assert db.scalar(select(User)).password_hash == stronger


def test_non_utf8_challenge_input_is_rejected_before_credential_processing(client):
    bodies = {
        "/v1/auth/refresh": b'{"refresh_token":"\\ud800"}',
        "/v1/auth/verification/confirm": b'{"token":"\\ud800"}',
        "/v1/auth/recovery/confirm": b'{"token":"\\ud800","password":"synthetic-password"}',
    }
    for endpoint, body in bodies.items():
        assert client.post(endpoint, content=body, headers={"Content-Type": "application/json"}).status_code == 422
    assert session_count() == 0
