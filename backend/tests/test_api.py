def register(client):
    response = client.post("/auth/register", json={"email": "user@example.com", "password": "password123"})
    assert response.status_code == 201
    return response.json()["access_token"]


def test_register_login_and_analysis(client):
    token = register(client)
    login = client.post("/auth/login", json={"email": "user@example.com", "password": "password123"})
    assert login.status_code == 200
    response = client.post("/analysis/analyze", headers={"Authorization": f"Bearer {token}"}, json={"content": "Urgent: send a gift card and your OTP immediately: https://bad.example"})
    assert response.status_code == 200
    assert response.json()["verdict"] == "high-risk"
    assert response.json()["score"] == 85


def test_analysis_requires_auth(client):
    assert client.post("/analysis/analyze", json={"content": "hello"}).status_code == 401


def test_duplicate_registration_rejected(client):
    register(client)
    assert client.post("/auth/register", json={"email": "USER@example.com", "password": "password123"}).status_code == 409


def test_history_is_authenticated_paginated_and_searchable(client):
    token = register(client)
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/analysis/analyze", headers=headers, json={"content": "first message"})
    client.post("/analysis/analyze", headers=headers, json={"content": "second urgent message"})

    response = client.get("/analysis/history?page=1&page_size=1&search=urgent", headers=headers)
    assert response.status_code == 200
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
