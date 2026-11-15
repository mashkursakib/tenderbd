"""Auth endpoints (SPEC.md section 4)."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import auth, config
from ..db import AppStore, get_store, now_utc, parse_dt
from ..services import email as email_service

router = APIRouter(prefix="/auth", tags=["auth"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SignupBody(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(max_length=254)
    password: str = Field(min_length=8, max_length=72)


class SigninBody(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=72)


class RequestResetBody(BaseModel):
    email: str = Field(max_length=254)


class ResetPasswordBody(BaseModel):
    email: str = Field(max_length=254)
    reset_token: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=72)


def _valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email.strip()))


@router.post("/signup")
def signup(body: SignupBody, store: AppStore = Depends(get_store)):
    email = body.email.strip().lower()
    if not _valid_email(email):
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    if auth.get_user_by_email(store, email) is not None:
        raise HTTPException(status_code=400,
                            detail=auth.DUPLICATE_EMAIL_ERROR)
    is_admin = email in config.admin_emails()
    now = now_utc()
    user_id = store.insert(
        "INSERT INTO users (email, password_hash, name, is_admin, "
        "created_at) VALUES (%(email)s, %(password_hash)s, %(name)s, "
        "%(is_admin)s, %(created_at)s)",
        {"email": email, "password_hash": auth.hash_password(body.password),
         "name": body.name.strip(), "is_admin": is_admin,
         "created_at": store.dt(now)})
    store.execute(
        "INSERT INTO subscriptions (user_id, plan, status, updated_at) "
        "VALUES (%(user_id)s, 'Free', 'Active', %(now)s)",
        {"user_id": user_id, "now": store.dt(now)})
    user = auth.get_user_by_id(store, user_id)
    token = auth.issue_session(store, user)
    return {"user": auth.public_user(store, user), "token": token}


@router.post("/signin")
def signin(body: SigninBody, store: AppStore = Depends(get_store)):
    email = body.email.strip().lower()
    if auth.is_locked(store, email):
        raise HTTPException(status_code=429, detail=auth.LOCKOUT_ERROR)
    user = auth.get_user_by_email(store, email)
    if user is None or not auth.verify_password(user["password_hash"],
                                                body.password):
        auth.record_failed_signin(store, email)
        raise HTTPException(status_code=401,
                            detail=auth.GENERIC_SIGNIN_ERROR)
    auth.clear_signin_attempts(store, email)
    token = auth.issue_session(store, user)
    return {"user": auth.public_user(store, user), "token": token}


@router.post("/signout")
def signout(user: dict = Depends(auth.get_current_user),
            store: AppStore = Depends(get_store)):
    auth.clear_session(store, user["id"])
    return {}


@router.get("/me")
def me(user: dict = Depends(auth.get_current_user),
       store: AppStore = Depends(get_store)):
    profile = store.fetchone(
        "SELECT id FROM companies WHERE user_id = %(user_id)s",
        {"user_id": user["id"]})
    pending = store.fetchone(
        "SELECT plan FROM payment_submissions WHERE user_id = %(user_id)s "
        "AND status = 'Pending' ORDER BY submitted_at DESC LIMIT 1",
        {"user_id": user["id"]})
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "plan": auth.get_plan(store, user["id"]),
        "is_admin": bool(user["is_admin"]),
        "has_profile": profile is not None,
        "pending_payment_plan": pending["plan"] if pending else None,
    }


@router.post("/request-password-reset")
def request_password_reset(body: RequestResetBody,
                           store: AppStore = Depends(get_store)):
    email = body.email.strip().lower()
    user = auth.get_user_by_email(store, email)
    if user is not None:
        token = auth.new_token()
        expires = now_utc() + auth.RESET_TTL
        store.execute(
            "UPDATE users SET reset_token = %(token)s, "
            "reset_expires_at = %(expires)s WHERE id = %(id)s",
            {"token": token, "expires": store.dt(expires),
             "id": user["id"]})
        email_service.send_password_reset_email(email, token)
    # Never reveal whether the account exists; never return the token.
    return {"message": auth.RESET_SENT_MESSAGE}


@router.post("/reset-password")
def reset_password(body: ResetPasswordBody,
                   store: AppStore = Depends(get_store)):
    email = body.email.strip().lower()
    user = auth.get_user_by_email(store, email)
    expires = parse_dt(user.get("reset_expires_at")) if user else None
    if (user is None or not user.get("reset_token")
            or user["reset_token"] != body.reset_token
            or expires is None or expires <= now_utc()):
        raise HTTPException(status_code=400,
                            detail=auth.RESET_INVALID_ERROR)
    store.execute(
        "UPDATE users SET password_hash = %(hash)s, reset_token = NULL, "
        "reset_expires_at = NULL WHERE id = %(id)s",
        {"hash": auth.hash_password(body.new_password), "id": user["id"]})
    auth.clear_signin_attempts(store, email)
    token = auth.issue_session(store, user)
    return {"user": auth.public_user(store, user), "token": token}
