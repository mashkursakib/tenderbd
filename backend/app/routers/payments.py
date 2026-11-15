"""Payment submissions (SPEC.md section 4).

Plans change only via admin payment approval or admin set-plan.
No subscription expiry, billing period, or renewal logic.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import auth, config
from ..db import AppStore, get_store, now_utc

router = APIRouter(prefix="/payments", tags=["payments"])

PENDING_PAYMENT_ERROR = (
    "You already have a payment waiting for verification. "
    "Please wait for it to be reviewed.")


class PaymentBody(BaseModel):
    plan: str = Field(pattern="^(Premium|Pro)$")
    method: str = Field(pattern="^(bKash|Nagad)$")
    transaction_id: str = Field(min_length=4, max_length=60)
    sender_number: str | None = Field(default=None, max_length=30)


@router.get("/mine")
def my_payments(user: dict = Depends(auth.get_current_user),
                store: AppStore = Depends(get_store)):
    return store.fetchall(
        "SELECT * FROM payment_submissions WHERE user_id = %(user_id)s "
        "ORDER BY submitted_at DESC, id DESC LIMIT 20",
        {"user_id": user["id"]})


@router.post("")
def submit_payment(body: PaymentBody,
                   user: dict = Depends(auth.get_current_user),
                   store: AppStore = Depends(get_store)):
    current = auth.get_plan(store, user["id"])
    if (config.PLAN_RANK.get(current, 0)
            >= config.PLAN_RANK[body.plan]):
        raise HTTPException(
            status_code=400,
            detail=f"You are already on the {body.plan} plan.")
    pending = store.fetchone(
        "SELECT id FROM payment_submissions WHERE user_id = %(user_id)s "
        "AND status = 'Pending' LIMIT 1",
        {"user_id": user["id"]})
    if pending is not None:
        raise HTTPException(status_code=400, detail=PENDING_PAYMENT_ERROR)
    submission_id = store.insert(
        "INSERT INTO payment_submissions (user_id, plan, method, "
        "transaction_id, sender_number, amount_bdt, status, "
        "submitted_at) VALUES (%(user_id)s, %(plan)s, %(method)s, "
        "%(transaction_id)s, %(sender_number)s, %(amount_bdt)s, "
        "'Pending', %(submitted_at)s)",
        {"user_id": user["id"], "plan": body.plan, "method": body.method,
         "transaction_id": body.transaction_id.strip(),
         "sender_number": body.sender_number,
         "amount_bdt": config.PLAN_PRICES_BDT[body.plan],
         "submitted_at": store.dt(now_utc())})
    return store.fetchone(
        "SELECT * FROM payment_submissions WHERE id = %(id)s",
        {"id": submission_id})
