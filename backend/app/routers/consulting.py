"""Consulting requests (SPEC.md section 4).

Creating a request is Premium+; reading your own requests is not gated.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import auth
from ..db import AppStore, get_store, now_utc

router = APIRouter(prefix="/consulting", tags=["consulting"])


class ConsultingBody(BaseModel):
    topic: str = Field(min_length=3, max_length=200)
    message: str = Field(min_length=10, max_length=3000)
    tender_id: int | None = None


@router.get("/mine")
def my_requests(user: dict = Depends(auth.get_current_user),
                store: AppStore = Depends(get_store)):
    return store.fetchall(
        "SELECT * FROM consulting_requests WHERE user_id = %(user_id)s "
        "ORDER BY created_at DESC, id DESC",
        {"user_id": user["id"]})


@router.post("")
def create_request(body: ConsultingBody,
                   user: dict = Depends(auth.get_current_user),
                   store: AppStore = Depends(get_store)):
    auth.require_plan(store, user, "Premium")
    tender_title = None
    if body.tender_id is not None:
        tender = store.get_tender(body.tender_id)
        if tender is None:
            raise HTTPException(status_code=404, detail="Tender not found.")
        tender_title = tender.get("title")
    request_id = store.insert(
        "INSERT INTO consulting_requests (user_id, tender_id, "
        "tender_title, topic, message, status, created_at) "
        "VALUES (%(user_id)s, %(tender_id)s, %(tender_title)s, "
        "%(topic)s, %(message)s, 'Open', %(created_at)s)",
        {"user_id": user["id"], "tender_id": body.tender_id,
         "tender_title": tender_title, "topic": body.topic.strip(),
         "message": body.message.strip(),
         "created_at": store.dt(now_utc())})
    return store.fetchone(
        "SELECT * FROM consulting_requests WHERE id = %(id)s",
        {"id": request_id})
