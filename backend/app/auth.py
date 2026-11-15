"""Authentication: argon2id passwords, 30-day session tokens,
per-email sign-in rate limiting, password-reset tokens, plan gates.

Error strings are verbatim from SPEC.md sections 4-6.
"""

from __future__ import annotations

import logging
import secrets
from datetime import timedelta

import argon2
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, Request

from . import config
from .db import AppStore, get_store, now_utc, parse_dt

log = logging.getLogger(__name__)

_hasher = PasswordHasher()

SESSION_TTL = timedelta(days=30)
RESET_TTL = timedelta(hours=1)
RATE_WINDOW = timedelta(minutes=15)
RATE_MAX_FAILURES = 5

GENERIC_SIGNIN_ERROR = "Email or password is incorrect. Check both and try again."
LOCKOUT_ERROR = "Too many failed sign-in attempts. Try again in a few minutes."
DUPLICATE_EMAIL_ERROR = (
    "An account with this email already exists. Sign in instead.")
RESET_INVALID_ERROR = (
    "That reset code is invalid or has expired. Request a new one.")
RESET_SENT_MESSAGE = (
    "If an account exists for that email, a reset link has been sent.")
ADMIN_ONLY_ERROR = "Admin access only."
FAVOURITE_CAP_ERROR = (
    "The Free plan keeps 3 favourites. "
    "Upgrade to Premium for unlimited favourites.")


def plan_gate_message(min_plan: str, current_plan: str) -> str:
    return (f"This is a {min_plan} feature. Your current plan is "
            f"{current_plan}. Upgrade from the Plans tab to unlock it.")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, argon2.exceptions.InvalidHashError,
            argon2.exceptions.VerificationError):
        return False


def new_token() -> str:
    """48-hex-char session/reset token (24 random bytes)."""
    return secrets.token_hex(24)


# -- users ---------------------------------------------------------------
def get_user_by_email(store: AppStore, email: str) -> dict | None:
    return store.fetchone(
        "SELECT * FROM users WHERE email = %(email)s",
        {"email": email.strip().lower()})


def get_user_by_id(store: AppStore, user_id: int) -> dict | None:
    return store.fetchone(
        "SELECT * FROM users WHERE id = %(id)s", {"id": user_id})


def get_user_by_token(store: AppStore, token: str) -> dict | None:
    return store.fetchone(
        "SELECT * FROM users WHERE session_token = %(token)s",
        {"token": token})


def get_plan(store: AppStore, user_id: int) -> str:
    row = store.fetchone(
        "SELECT plan FROM subscriptions WHERE user_id = %(user_id)s",
        {"user_id": user_id})
    return row["plan"] if row else "Free"


def public_user(store: AppStore, user: dict) -> dict:
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "plan": get_plan(store, user["id"]),
        "is_admin": bool(user["is_admin"]),
    }


def issue_session(store: AppStore, user: dict) -> str:
    """New 30-day session; invalidates any previous token."""
    token = new_token()
    expires = now_utc() + SESSION_TTL
    store.execute(
        "UPDATE users SET session_token = %(token)s, "
        "session_expires_at = %(expires)s WHERE id = %(id)s",
        {"token": token, "expires": store.dt(expires), "id": user["id"]})
    return token


def clear_session(store: AppStore, user_id: int) -> None:
    store.execute(
        "UPDATE users SET session_token = NULL, "
        "session_expires_at = NULL WHERE id = %(id)s",
        {"id": user_id})


# -- rate limiting -------------------------------------------------------
def _attempts_row(store: AppStore, email: str) -> dict | None:
    return store.fetchone(
        "SELECT * FROM sign_in_attempts WHERE email = %(email)s",
        {"email": email})


def is_locked(store: AppStore, email: str) -> bool:
    row = _attempts_row(store, email)
    if not row:
        return False
    locked_until = parse_dt(row.get("locked_until"))
    return bool(locked_until and locked_until > now_utc())


def record_failed_signin(store: AppStore, email: str) -> None:
    now = now_utc()
    row = _attempts_row(store, email)
    if row is None:
        store.execute(
            "INSERT INTO sign_in_attempts (email, fail_count, "
            "window_started_at) VALUES (%(email)s, 1, %(now)s)",
            {"email": email, "now": store.dt(now)})
        return
    window_start = parse_dt(row["window_started_at"]) or now
    if now - window_start >= RATE_WINDOW:
        fail_count, window_start = 1, now
    else:
        fail_count = (row["fail_count"] or 0) + 1
    locked_until = None
    if fail_count >= RATE_MAX_FAILURES:
        locked_until = now + RATE_WINDOW
    store.execute(
        "UPDATE sign_in_attempts SET fail_count = %(count)s, "
        "window_started_at = %(window)s, locked_until = %(locked)s "
        "WHERE email = %(email)s",
        {"count": fail_count, "window": store.dt(window_start),
         "locked": store.dt(locked_until), "email": email})


def clear_signin_attempts(store: AppStore, email: str) -> None:
    store.execute(
        "DELETE FROM sign_in_attempts WHERE email = %(email)s",
        {"email": email})


# -- FastAPI dependencies ------------------------------------------------
def _bearer_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def _authenticate(store: AppStore, token: str | None) -> dict | None:
    """Validate a session token; clears expired tokens server-side."""
    if not token:
        return None
    user = get_user_by_token(store, token)
    if user is None:
        return None
    expires = parse_dt(user.get("session_expires_at"))
    if expires is None or expires <= now_utc():
        clear_session(store, user["id"])
        return None
    return user


def get_current_user(request: Request,
                     store: AppStore = Depends(get_store)) -> dict:
    user = _authenticate(store, _bearer_token(request))
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def get_optional_user(request: Request,
                      store: AppStore = Depends(get_store)) -> dict | None:
    return _authenticate(store, _bearer_token(request))


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail=ADMIN_ONLY_ERROR)
    return user


def require_plan(store: AppStore, user: dict, min_plan: str) -> str:
    """Enforce a plan gate; returns the user's current plan."""
    current = get_plan(store, user["id"])
    if config.PLAN_RANK.get(current, 0) < config.PLAN_RANK[min_plan]:
        raise HTTPException(
            status_code=403,
            detail=plan_gate_message(min_plan, current))
    return current
