"""Admin endpoints (SPEC.md section 4). is_admin only."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import auth
from ..db import AppStore, get_store, now_utc

router = APIRouter(prefix="/admin", tags=["admin"])

ALREADY_REVIEWED_ERROR = "That payment was already reviewed."


class ReviewBody(BaseModel):
    approve: bool
    note: str | None = Field(default=None, max_length=500)


class ReplyBody(BaseModel):
    reply: str = Field(min_length=2, max_length=4000)


class SetPlanBody(BaseModel):
    plan: str = Field(pattern="^(Free|Premium|Pro)$")


def _counts_by_user(store: AppStore, table: str) -> dict[int, int]:
    rows = store.fetchall(
        f"SELECT user_id, COUNT(*) AS n FROM {table} GROUP BY user_id")
    return {row["user_id"]: row["n"] for row in rows}


@router.get("/overview")
def overview(admin: dict = Depends(auth.require_admin),
             store: AppStore = Depends(get_store)):
    totals_row = store.fetchone(
        "SELECT COUNT(*) AS users FROM users")
    plan_rows = store.fetchall(
        "SELECT plan, COUNT(*) AS n FROM subscriptions GROUP BY plan")
    plan_counts = {row["plan"]: row["n"] for row in plan_rows}
    pending = store.fetchone(
        "SELECT COUNT(*) AS n FROM payment_submissions "
        "WHERE status = 'Pending'")
    open_consulting = store.fetchone(
        "SELECT COUNT(*) AS n FROM consulting_requests "
        "WHERE status = 'Open'")
    tender_count = store.fetchone("SELECT COUNT(*) AS n FROM tenders")

    users = store.fetchall(
        "SELECT id, name, email, is_admin, created_at FROM users "
        "ORDER BY created_at DESC, id DESC")
    companies = {row["user_id"]: row["company_name"] for row in
                 store.fetchall(
                     "SELECT user_id, company_name FROM companies")}
    plans = {row["user_id"]: row["plan"] for row in
             store.fetchall("SELECT user_id, plan FROM subscriptions")}
    alert_users = {row["user_id"] for row in
                   store.fetchall("SELECT user_id FROM alert_prefs")}
    fav_counts = _counts_by_user(store, "favourites")
    doc_counts = _counts_by_user(store, "documents")
    jv_counts = _counts_by_user(store, "jv_posts")
    consulting_counts = _counts_by_user(store, "consulting_requests")

    user_list = []
    for user in users:
        user_id = user["id"]
        user_list.append({
            "id": user_id,
            "name": user["name"],
            "email": user["email"],
            "company": companies.get(user_id),
            "plan": plans.get(user_id, "Free"),
            "is_admin": bool(user["is_admin"]),
            "signed_up_at": user["created_at"],
            "counts": {
                "favourites": fav_counts.get(user_id, 0),
                "documents": doc_counts.get(user_id, 0),
                "jv_posts": jv_counts.get(user_id, 0),
                "consulting_requests": consulting_counts.get(user_id, 0),
            },
            "has_alert_prefs": user_id in alert_users,
        })

    payments = store.fetchall(
        "SELECT * FROM payment_submissions "
        "ORDER BY submitted_at DESC, id DESC LIMIT 100")
    consulting = store.fetchall(
        "SELECT * FROM consulting_requests "
        "ORDER BY created_at DESC, id DESC LIMIT 100")
    return {
        "totals": {
            "users": totals_row["users"],
            "premium": plan_counts.get("Premium", 0),
            "pro": plan_counts.get("Pro", 0),
            "pending_payments": pending["n"],
            "open_consulting": open_consulting["n"],
            "tenders": tender_count["n"],
        },
        "users": user_list,
        "payments": payments,
        "consulting": consulting,
    }


@router.post("/payments/{submission_id}/review")
def review_payment(submission_id: int, body: ReviewBody,
                   admin: dict = Depends(auth.require_admin),
                   store: AppStore = Depends(get_store)):
    submission = store.fetchone(
        "SELECT * FROM payment_submissions WHERE id = %(id)s",
        {"id": submission_id})
    if submission is None:
        raise HTTPException(status_code=404, detail="Payment not found.")
    if submission["status"] != "Pending":
        raise HTTPException(status_code=400,
                            detail=ALREADY_REVIEWED_ERROR)
    now = now_utc()
    status = "Approved" if body.approve else "Rejected"
    store.execute(
        "UPDATE payment_submissions SET status = %(status)s, "
        "reviewed_at = %(reviewed_at)s, review_note = %(note)s "
        "WHERE id = %(id)s",
        {"status": status, "reviewed_at": store.dt(now),
         "note": body.note, "id": submission_id})
    if body.approve:
        store.execute(
            "INSERT INTO subscriptions (user_id, plan, payment_method, "
            "status, updated_at) VALUES (%(user_id)s, %(plan)s, "
            "%(method)s, 'Active', %(now)s) "
            "ON CONFLICT (user_id) DO UPDATE SET plan = EXCLUDED.plan, "
            "payment_method = EXCLUDED.payment_method, "
            "status = 'Active', updated_at = EXCLUDED.updated_at",
            {"user_id": submission["user_id"], "plan": submission["plan"],
             "method": submission["method"], "now": store.dt(now)})
    return store.fetchone(
        "SELECT * FROM payment_submissions WHERE id = %(id)s",
        {"id": submission_id})


@router.post("/consulting/{request_id}/reply")
def reply_consulting(request_id: int, body: ReplyBody,
                     admin: dict = Depends(auth.require_admin),
                     store: AppStore = Depends(get_store)):
    request = store.fetchone(
        "SELECT * FROM consulting_requests WHERE id = %(id)s",
        {"id": request_id})
    if request is None:
        raise HTTPException(status_code=404,
                            detail="Consulting request not found.")
    store.execute(
        "UPDATE consulting_requests SET reply = %(reply)s, "
        "status = 'Answered', replied_at = %(replied_at)s "
        "WHERE id = %(id)s",
        {"reply": body.reply.strip(), "replied_at": store.dt(now_utc()),
         "id": request_id})
    return store.fetchone(
        "SELECT * FROM consulting_requests WHERE id = %(id)s",
        {"id": request_id})


@router.post("/users/{user_id}/plan")
def set_user_plan(user_id: int, body: SetPlanBody,
                  admin: dict = Depends(auth.require_admin),
                  store: AppStore = Depends(get_store)):
    user = auth.get_user_by_id(store, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    store.execute(
        "INSERT INTO subscriptions (user_id, plan, payment_method, "
        "status, updated_at) VALUES (%(user_id)s, %(plan)s, 'Admin', "
        "'Active', %(now)s) "
        "ON CONFLICT (user_id) DO UPDATE SET plan = EXCLUDED.plan, "
        "payment_method = 'Admin', status = 'Active', "
        "updated_at = EXCLUDED.updated_at",
        {"user_id": user_id, "plan": body.plan,
         "now": store.dt(now_utc())})
    return {"user_id": user_id, "plan": body.plan,
            "payment_method": "Admin", "status": "Active"}
