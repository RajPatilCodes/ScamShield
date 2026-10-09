from uuid import uuid4
from app.email_delivery import captures
from app.privacy_config import PURPOSE, NOTICE_VERSION
from app.database import SessionLocal
from app.privacy_models import PrivacyJob
from app.privacy_jobs import process_job

PASSWORD = "synthetic-password-123"


def account(client, email="privacy@example.com"):
    assert client.post("/v1/auth/register", json={"email": email, "password": PASSWORD}).status_code == 201
    assert client.post("/v1/auth/verification/confirm", json={"token": captures[-1].token}).status_code == 204
    response = client.post("/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200
    return response.json()


def headers(tokens, key=None):
    return {"Authorization": f"Bearer {tokens['access_token']}", "Idempotency-Key": key or str(uuid4())}


def consent(client, tokens, granted=True, expected=None):
    if expected is None:
        expected = client.get("/v1/privacy", headers=headers(tokens)).json()["preference_version"]
    return client.put(f"/v1/privacy/consents/{PURPOSE}", headers=headers(tokens), json={
        "granted": granted, "version": NOTICE_VERSION, "expected_version": expected})


def save(client, tokens, content="synthetic private message", key=None):
    return client.post("/v1/privacy/analyses", headers=headers(tokens, key), json={"content": content, "save": True})


def grant(client, tokens, action, target="self"):
    response = client.post("/v1/privacy/reauthenticate", headers=headers(tokens), json={
        "password": PASSWORD, "action": action, "target": target})
    assert response.status_code == 200, response.text
    return response.json()["grant"]


def drain(job_id):
    while True:
        with SessionLocal() as db:
            job = db.get(PrivacyJob, job_id)
            if not job or job.state not in ("queued", "retrying"):
                return job.state if job else None
        if not process_job(job_id):
            with SessionLocal() as db:
                return db.get(PrivacyJob, job_id).state
