"""Auth tests: signup/signin/signout, rate-limit lockout, generic
errors, password reset flow."""

from datetime import datetime, timedelta, timezone

from backend.tests.helpers import ADMIN_EMAIL, auth_headers, make_user, signup


def test_signup_success(client):
    data = signup(client, "new@example.com")
    assert data["user"]["email"] == "new@example.com"
    assert data["user"]["name"] == "Test User"
    assert data["user"]["plan"] == "Free"
    assert data["user"]["is_admin"] is False
    assert len(data["token"]) == 48
    assert all(c in "0123456789abcdef" for c in data["token"])


def test_signup_duplicate_email(client):
    signup(client, "dup@example.com")
    resp = client.post("/api/v1/auth/signup", json={
        "name": "Other", "email": "DUP@example.com",
        "password": "password123"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == (
        "An account with this email already exists. Sign in instead.")


def test_signup_admin_email(client):
    data = signup(client, ADMIN_EMAIL, name="Admin")
    assert data["user"]["is_admin"] is True


def test_signup_validation(client):
    resp = client.post("/api/v1/auth/signup", json={
        "name": "A", "email": "x@example.com", "password": "password123"})
    assert resp.status_code == 422  # name too short
    resp = client.post("/api/v1/auth/signup", json={
        "name": "Valid Name", "email": "x@example.com",
        "password": "short"})
    assert resp.status_code == 422  # password too short
    resp = client.post("/api/v1/auth/signup", json={
        "name": "Valid Name", "email": "not-an-email",
        "password": "password123"})
    assert resp.status_code == 400


def test_signin_success_and_me(client):
    signup(client, "me@example.com")
    resp = client.post("/api/v1/auth/signin", json={
        "email": "me@example.com", "password": "password123"})
    assert resp.status_code == 200
    token = resp.json()["token"]
    me = client.get("/api/v1/auth/me", headers=auth_headers(token))
    assert me.status_code == 200
    assert me.json()["email"] == "me@example.com"
    assert me.json()["has_profile"] is False
    assert me.json()["pending_payment_plan"] is None


def test_signin_wrong_password_generic_error(client):
    signup(client, "wrong@example.com")
    resp = client.post("/api/v1/auth/signin", json={
        "email": "wrong@example.com", "password": "nope-nope-nope"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == (
        "Email or password is incorrect. Check both and try again.")


def test_signin_unknown_email_generic_error(client):
    resp = client.post("/api/v1/auth/signin", json={
        "email": "nobody@example.com", "password": "password123"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == (
        "Email or password is incorrect. Check both and try again.")


def test_signin_new_token_invalidates_old(client):
    user, token1 = make_user(client, "rotate@example.com")
    resp = client.post("/api/v1/auth/signin", json={
        "email": "rotate@example.com", "password": "password123"})
    token2 = resp.json()["token"]
    assert token2 != token1
    assert client.get("/api/v1/auth/me",
                      headers=auth_headers(token1)).status_code == 401
    assert client.get("/api/v1/auth/me",
                      headers=auth_headers(token2)).status_code == 200


def test_signout_invalidates_token(client):
    _, token = make_user(client, "out@example.com")
    resp = client.post("/api/v1/auth/signout", headers=auth_headers(token))
    assert resp.status_code == 200
    assert client.get("/api/v1/auth/me",
                      headers=auth_headers(token)).status_code == 401


def test_me_requires_auth(client):
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me",
                      headers=auth_headers("0" * 48)).status_code == 401


def test_expired_session_cleared(client, store):
    user, token = make_user(client, "expired@example.com")
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    store.execute(
        "UPDATE users SET session_expires_at = %(exp)s WHERE id = %(id)s",
        {"exp": store.dt(past), "id": user["id"]})
    assert client.get("/api/v1/auth/me",
                      headers=auth_headers(token)).status_code == 401
    row = store.fetchone("SELECT session_token FROM users WHERE id = %(id)s",
                         {"id": user["id"]})
    assert row["session_token"] is None


def test_rate_limit_lockout(client):
    signup(client, "locked@example.com")
    for _ in range(5):
        resp = client.post("/api/v1/auth/signin", json={
            "email": "locked@example.com", "password": "wrong-password"})
        assert resp.status_code == 401
    resp = client.post("/api/v1/auth/signin", json={
        "email": "locked@example.com", "password": "wrong-password"})
    assert resp.status_code == 429
    assert resp.json()["detail"] == (
        "Too many failed sign-in attempts. Try again in a few minutes.")
    # Even the right password is locked out.
    resp = client.post("/api/v1/auth/signin", json={
        "email": "locked@example.com", "password": "password123"})
    assert resp.status_code == 429


def test_rate_limit_success_clears_attempts(client):
    signup(client, "clear@example.com")
    for _ in range(4):
        client.post("/api/v1/auth/signin", json={
            "email": "clear@example.com", "password": "wrong-password"})
    resp = client.post("/api/v1/auth/signin", json={
        "email": "clear@example.com", "password": "password123"})
    assert resp.status_code == 200
    # Four more failures after the success: still 401, not locked.
    for _ in range(4):
        resp = client.post("/api/v1/auth/signin", json={
            "email": "clear@example.com", "password": "wrong-password"})
        assert resp.status_code == 401


def test_request_reset_always_same_message(client):
    signup(client, "reset@example.com")
    for email in ("reset@example.com", "ghost@example.com"):
        resp = client.post("/api/v1/auth/request-password-reset",
                           json={"email": email})
        assert resp.status_code == 200
        assert resp.json() == {
            "message": "If an account exists for that email, a reset "
                       "link has been sent."}
        assert "reset_token" not in resp.text


def test_reset_password_flow(client, store):
    user, _ = make_user(client, "flow@example.com")
    client.post("/api/v1/auth/request-password-reset",
                json={"email": "flow@example.com"})
    row = store.fetchone(
        "SELECT reset_token, reset_expires_at FROM users "
        "WHERE id = %(id)s", {"id": user["id"]})
    assert row["reset_token"]
    resp = client.post("/api/v1/auth/reset-password", json={
        "email": "flow@example.com", "reset_token": row["reset_token"],
        "new_password": "newpassword456"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["user"]["email"] == "flow@example.com"
    # New password works; old one does not.
    assert client.post("/api/v1/auth/signin", json={
        "email": "flow@example.com",
        "password": "newpassword456"}).status_code == 200
    assert client.post("/api/v1/auth/signin", json={
        "email": "flow@example.com",
        "password": "password123"}).status_code == 401
    # Token is single-use.
    resp = client.post("/api/v1/auth/reset-password", json={
        "email": "flow@example.com", "reset_token": row["reset_token"],
        "new_password": "anotherpass789"})
    assert resp.status_code == 400


def test_reset_password_bad_token(client):
    signup(client, "badtoken@example.com")
    resp = client.post("/api/v1/auth/reset-password", json={
        "email": "badtoken@example.com", "reset_token": "deadbeef",
        "new_password": "newpassword456"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == (
        "That reset code is invalid or has expired. Request a new one.")


def test_reset_password_expired_token(client, store):
    user, _ = make_user(client, "expiredtoken@example.com")
    client.post("/api/v1/auth/request-password-reset",
                json={"email": "expiredtoken@example.com"})
    row = store.fetchone(
        "SELECT reset_token FROM users WHERE id = %(id)s",
        {"id": user["id"]})
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    store.execute(
        "UPDATE users SET reset_expires_at = %(exp)s WHERE id = %(id)s",
        {"exp": store.dt(past), "id": user["id"]})
    resp = client.post("/api/v1/auth/reset-password", json={
        "email": "expiredtoken@example.com",
        "reset_token": row["reset_token"], "new_password": "newpassword456"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == (
        "That reset code is invalid or has expired. Request a new one.")
