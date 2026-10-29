from __future__ import annotations

import uuid


def test_health_reports_database(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


def test_private_endpoints_require_token(client):
    for path in (
        "/api/v1/notes",
        "/api/v1/me",
        "/api/v1/progress",
        "/api/v1/quizzes/daily",
        "/api/v1/revision/due",
    ):
        assert client.get(path).status_code == 401, path


def test_invalid_expired_and_forged_tokens_rejected(client, make_user, token):
    user = make_user()
    expired = token(str(user.id), ttl=-60)
    forged = token(str(user.id), secret="not-the-real-secret-0123456789-abcdefgh")
    too_long = token(str(user.id), ttl=7200)
    for bad in (expired, forged, too_long, "garbage"):
        res = client.get("/api/v1/me", headers={"Authorization": f"Bearer {bad}"})
        assert res.status_code == 401


def test_unknown_user_subject_rejected(client, token):
    res = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token(str(uuid.uuid4()))}"})
    assert res.status_code == 401


def test_user_sync_requires_internal_scope(client, make_user, token, auth):
    payload = {"auth_provider_id": "demo:rimi", "display_name": "Rimi"}
    assert client.post("/api/v1/auth/sync", json=payload).status_code == 401
    user = make_user()
    assert client.post("/api/v1/auth/sync", json=payload, headers=auth(user)).status_code == 403
    internal = {"Authorization": f"Bearer {token('aks-web', scope='internal')}"}
    res = client.post("/api/v1/auth/sync", json=payload, headers=internal)
    assert res.status_code == 200
    body = res.json()
    assert body["display_name"] == "Rimi"
    assert body["is_admin"] is False
    # idempotent: same provider id -> same user
    again = client.post("/api/v1/auth/sync", json=payload, headers=internal).json()
    assert again["user_id"] == body["user_id"]


def test_admin_role_from_config_not_from_token(client, token):
    internal = {"Authorization": f"Bearer {token('aks-web', scope='internal')}"}
    demo_admin = client.post(
        "/api/v1/auth/sync",
        json={"auth_provider_id": "demo:admin", "display_name": "Admin"},
        headers=internal,
    ).json()
    boss = client.post(
        "/api/v1/auth/sync",
        json={"auth_provider_id": "github:42", "display_name": "Boss", "email": "Boss@Example.com"},
        headers=internal,
    ).json()
    regular = client.post(
        "/api/v1/auth/sync", json={"auth_provider_id": "github:43", "display_name": "Reg"}, headers=internal
    ).json()
    assert demo_admin["is_admin"] and boss["is_admin"]
    assert not regular["is_admin"]
    # A user token cannot claim admin rights through extra claims.
    forged_claims = {"Authorization": f"Bearer {token(regular['user_id'], is_admin=True, role='admin')}"}
    assert client.get("/api/v1/admin/overview", headers=forged_claims).status_code == 403
    admin_headers = {"Authorization": f"Bearer {token(demo_admin['user_id'])}"}
    assert client.get("/api/v1/admin/overview", headers=admin_headers).status_code == 200


def test_all_admin_endpoints_forbidden_for_regular_users(client, make_user, auth):
    headers = auth(make_user())
    event_id = uuid.uuid4()
    calls = [
        ("get", "/api/v1/admin/overview", None),
        ("get", "/api/v1/admin/jobs", None),
        ("get", "/api/v1/admin/ai/usage", None),
        ("get", "/api/v1/admin/review-queue", None),
        ("post", "/api/v1/admin/ingestion/run", {}),
        ("post", f"/api/v1/admin/events/{event_id}/approve", {}),
        ("post", f"/api/v1/admin/events/{event_id}/reject", {}),
        ("post", "/api/v1/admin/sources/pib/toggle", {"enabled": False}),
    ]
    for method, path, body in calls:
        res = getattr(client, method)(path, headers=headers, **({"json": body} if body is not None else {}))
        assert res.status_code == 403, path


def test_rate_limit_returns_429(client, make_user, auth):
    headers = auth(make_user())
    codes = [client.put("/api/v1/me/preferences", json={}, headers=headers).status_code for _ in range(32)]
    assert 429 in codes
