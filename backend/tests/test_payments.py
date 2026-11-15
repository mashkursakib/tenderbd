"""Payment submission tests: submit, duplicate-pending rejection,
admin approval activates the plan."""

from backend.tests.helpers import (auth_headers, make_admin, make_premium_user,
                      make_user)


def _submit(client, token, **overrides):
    body = {"plan": "Premium", "method": "bKash",
            "transaction_id": "TXN12345", "sender_number": "01700000000"}
    body.update(overrides)
    return client.post("/api/v1/payments", json=body,
                       headers=auth_headers(token))


def test_submit_payment(client, store):
    _, token = make_user(client, "pay@example.com")
    resp = _submit(client, token)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["plan"] == "Premium"
    assert body["method"] == "bKash"
    assert body["amount_bdt"] == 399
    assert body["status"] == "Pending"
    assert body["transaction_id"] == "TXN12345"
    mine = client.get("/api/v1/payments/mine",
                      headers=auth_headers(token)).json()
    assert len(mine) == 1
    me = client.get("/api/v1/auth/me", headers=auth_headers(token)).json()
    assert me["pending_payment_plan"] == "Premium"
    assert me["plan"] == "Free"  # not active until approved


def test_submit_pro_price(client, store):
    _, token = make_user(client, "paypro@example.com")
    resp = _submit(client, token, plan="Pro", method="Nagad",
                   transaction_id="NGD99999")
    assert resp.json()["amount_bdt"] == 799


def test_duplicate_pending_rejected(client, store):
    _, token = make_user(client, "paydup@example.com")
    assert _submit(client, token).status_code == 200
    resp = _submit(client, token, transaction_id="TXN99999")
    assert resp.status_code == 400
    assert resp.json()["detail"].startswith(
        "You already have a payment waiting for verification")
    # A different plan is still blocked while one is pending.
    resp = _submit(client, token, plan="Pro", transaction_id="TXN88888")
    assert resp.status_code == 400


def test_submit_validation(client, store):
    _, token = make_user(client, "payval@example.com")
    resp = _submit(client, token, plan="Gold")
    assert resp.status_code == 422
    resp = _submit(client, token, method="Card")
    assert resp.status_code == 422
    resp = _submit(client, token, transaction_id="abc")
    assert resp.status_code == 422


def test_admin_approve_activates_plan(client, store):
    _, token = make_user(client, "approve@example.com")
    submission = _submit(client, token).json()
    _, admin_token = make_admin(client, store)
    resp = client.post(
        f"/api/v1/admin/payments/{submission['id']}/review",
        json={"approve": True, "note": "Verified on bKash."},
        headers=auth_headers(admin_token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "Approved"
    assert resp.json()["review_note"] == "Verified on bKash."
    assert resp.json()["reviewed_at"] is not None
    me = client.get("/api/v1/auth/me", headers=auth_headers(token)).json()
    assert me["plan"] == "Premium"
    assert me["pending_payment_plan"] is None
    # Premium features now work.
    assert client.put("/api/v1/alerts", json={"keywords": "road"},
                      headers=auth_headers(token)).status_code == 200


def test_admin_reject_keeps_free_plan(client, store):
    _, token = make_user(client, "reject@example.com")
    submission = _submit(client, token).json()
    _, admin_token = make_admin(client, store)
    resp = client.post(
        f"/api/v1/admin/payments/{submission['id']}/review",
        json={"approve": False, "note": "Transaction not found."},
        headers=auth_headers(admin_token))
    assert resp.json()["status"] == "Rejected"
    me = client.get("/api/v1/auth/me", headers=auth_headers(token)).json()
    assert me["plan"] == "Free"
    # After rejection a fresh submission is allowed.
    assert _submit(client, token,
                   transaction_id="TXN77777").status_code == 200


def test_review_already_reviewed(client, store):
    _, token = make_user(client, "re-review@example.com")
    submission = _submit(client, token).json()
    _, admin_token = make_admin(client, store)
    url = f"/api/v1/admin/payments/{submission['id']}/review"
    assert client.post(url, json={"approve": True},
                       headers=auth_headers(admin_token)).status_code == 200
    resp = client.post(url, json={"approve": True},
                       headers=auth_headers(admin_token))
    assert resp.status_code == 400
    assert resp.json()["detail"] == "That payment was already reviewed."


def test_submit_already_on_plan(client, store):
    _, token = make_premium_user(client, store, "already@example.com")
    resp = _submit(client, token)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "You are already on the Premium plan."
    # Premium user CAN submit for Pro (a higher plan).
    resp = _submit(client, token, plan="Pro", transaction_id="TXN55555")
    assert resp.status_code == 200


def test_review_requires_admin(client, store):
    _, token = make_user(client, "nonadmin@example.com")
    submission = _submit(client, token).json()
    resp = client.post(
        f"/api/v1/admin/payments/{submission['id']}/review",
        json={"approve": True}, headers=auth_headers(token))
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin access only."
