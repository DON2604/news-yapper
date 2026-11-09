from __future__ import annotations


def test_register_and_login_with_email_password(client):
    created = client.post(
        "/api/v1/auth/register",
        json={"email": "Rimi@Example.com", "password": "correct-horse", "display_name": "Rimi"},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["email"] == "rimi@example.com"
    assert body["auth_provider_id"] == "password:rimi@example.com"
    assert body["display_name"] == "Rimi"
    assert "password" not in body

    again = client.post(
        "/api/v1/auth/register",
        json={"email": "rimi@example.com", "password": "another-password", "display_name": "Rimi"},
    )
    assert again.status_code == 409

    bad = client.post("/api/v1/auth/login", json={"email": "rimi@example.com", "password": "wrong-password"})
    assert bad.status_code == 401

    good = client.post("/api/v1/auth/login", json={"email": "RIMI@example.com", "password": "correct-horse"})
    assert good.status_code == 200
    assert good.json()["auth_provider_id"] == body["auth_provider_id"]


def test_login_unknown_email_is_rejected(client):
    res = client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "long-enough"})
    assert res.status_code == 401


def test_short_password_rejected(client):
    res = client.post(
        "/api/v1/auth/register",
        json={"email": "short@example.com", "password": "tiny", "display_name": "Short"},
    )
    assert res.status_code == 422
