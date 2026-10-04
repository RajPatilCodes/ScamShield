from app.email_delivery import captures


def register(client):
    response = client.post("/v1/auth/register", json={"email": "user@example.com", "password": "password123"})
    assert response.status_code == 201
    assert "access_token" not in response.json()
    assert client.post("/v1/auth/verification/confirm", json={"token": captures[-1].token}).status_code == 204
    login = client.post("/v1/auth/login", json={"email": "user@example.com", "password": "password123"})
    assert login.status_code == 200
    body = login.json()
    assert set(body) == {"access_token", "token_type", "refresh_token", "session_id", "expires_in"}
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    return body["access_token"]


def test_register_login_and_analysis(client):
    token = register(client)
    login = client.post("/v1/auth/login", json={"email": "user@example.com", "password": "password123"})
    assert login.status_code == 200
    assert set(login.json()) == {"access_token", "token_type", "refresh_token", "session_id", "expires_in"}
    assert login.json()["token_type"] == "bearer"
    response = client.post("/analysis/analyze", headers={"Authorization": f"Bearer {token}"}, json={"content": "Urgent: send a gift card and your OTP immediately: https://bad.example"})
    assert response.status_code == 200
    assert set(response.json()) == {"score", "verdict", "flags"}
    assert response.json()["verdict"] == "high-risk"
    assert response.json()["score"] == 85


def test_analysis_requires_auth(client):
    assert client.post("/analysis/analyze", json={"content": "hello"}).status_code == 401


def test_duplicate_registration_does_not_enumerate(client):
    register(client)
    assert client.post("/v1/auth/register", json={"email": "USER@example.com", "password": "password123"}).status_code == 201


def test_history_is_authenticated_paginated_and_searchable(client):
    token = register(client)
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/analysis/analyze", headers=headers, json={"content": "first message"})
    client.post("/analysis/analyze", headers=headers, json={"content": "second urgent message"})

    response = client.get("/analysis/history?page=1&page_size=1&search=urgent", headers=headers)
    assert response.status_code == 200
    assert set(response.json()) == {"items", "page", "page_size", "total"}
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["content"] == "second urgent message"
    assert client.get("/analysis/history").status_code == 401


def test_blank_analysis_content_rejected(client):
    token = register(client)
    response = client.post(
        "/analysis/analyze",
        headers={"Authorization": f"Bearer {token}"},
        json={"content": "   "},
    )
    assert response.status_code == 422
