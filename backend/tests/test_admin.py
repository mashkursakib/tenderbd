"""Admin overview + set-plan tests."""

from backend.tests.helpers import (auth_headers, make_admin, make_premium_user,
                      make_pro_user, make_user, save_profile, set_plan)


def test_overview_requires_admin(client, store):
    _, token = make_user(client, "noadmin@example.com")
    resp = client.get("/api/v1/admin/overview",
                      headers=auth_headers(token))
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin access only."
    assert client.get("/api/v1/admin/overview").status_code == 401


def test_overview_totals_and_users(client, store):
    _, admin_token = make_admin(client, store)
    user1, token1 = make_user(client, "u1@example.com")
    user2, token2 = make_premium_user(client, store, "u2@example.com")
    user3, _ = make_pro_user(client, store, "u3@example.com")
    save_profile(client, token2)
    client.post("/api/v1/favourites/1001/toggle",
                headers=auth_headers(token2))
    client.post("/api/v1/payments",
                json={"plan": "Premium", "method": "bKash",
                      "transaction_id": "TXN11111"},
                headers=auth_headers(token1))
    client.post("/api/v1/consulting",
                json={"topic": "Help needed",
                      "message": "Please help me with this tender."},
                headers=auth_headers(token2))

    body = client.get("/api/v1/admin/overview",
                      headers=auth_headers(admin_token)).json()
    assert body["totals"] == {
        "users": 4, "premium": 1, "pro": 1, "pending_payments": 1,
        "open_consulting": 1, "tenders": 5}
    assert len(body["users"]) == 4
    assert len(body["payments"]) == 1
    assert len(body["consulting"]) == 1
    by_email = {u["email"]: u for u in body["users"]}
    assert by_email["u2@example.com"]["plan"] == "Premium"
    assert by_email["u2@example.com"]["company"] == "Test Builders Ltd"
    assert by_email["u2@example.com"]["counts"]["favourites"] == 1
    assert by_email["u2@example.com"]["counts"]["consulting_requests"] == 1
    assert by_email["u2@example.com"]["has_alert_prefs"] is False
    assert by_email["u1@example.com"]["plan"] == "Free"
    assert by_email["u1@example.com"]["company"] is None
    assert by_email["u3@example.com"]["plan"] == "Pro"
    assert by_email["admin@example.com"]["is_admin"] is True
    for user in body["users"]:
        assert user["signed_up_at"] is not None


def test_set_plan(client, store):
    _, admin_token = make_admin(client, store)
    user, token = make_user(client, "setplan@example.com")
    resp = client.post(f"/api/v1/admin/users/{user['id']}/plan",
                       json={"plan": "Pro"},
                       headers=auth_headers(admin_token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["plan"] == "Pro"
    assert resp.json()["payment_method"] == "Admin"
    me = client.get("/api/v1/auth/me", headers=auth_headers(token)).json()
    assert me["plan"] == "Pro"
    # Downgrade works too.
    resp = client.post(f"/api/v1/admin/users/{user['id']}/plan",
                       json={"plan": "Free"},
                       headers=auth_headers(admin_token))
    assert resp.json()["plan"] == "Free"
    me = client.get("/api/v1/auth/me", headers=auth_headers(token)).json()
    assert me["plan"] == "Free"


def test_set_plan_missing_user_and_non_admin(client, store):
    _, admin_token = make_admin(client, store)
    resp = client.post("/api/v1/admin/users/999999/plan",
                       json={"plan": "Pro"},
                       headers=auth_headers(admin_token))
    assert resp.status_code == 404
    _, token = make_user(client, "setplan2@example.com")
    user, _ = make_user(client, "setplan3@example.com")
    resp = client.post(f"/api/v1/admin/users/{user['id']}/plan",
                       json={"plan": "Pro"}, headers=auth_headers(token))
    assert resp.status_code == 403
    resp = client.post(f"/api/v1/admin/users/{user['id']}/plan",
                       json={"plan": "Gold"},
                       headers=auth_headers(admin_token))
    assert resp.status_code == 422
