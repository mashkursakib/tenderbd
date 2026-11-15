"""Favourites + bid pipeline (SPEC.md section 4).

Toggle is open to all plans; the Free plan is capped at 3 favourites.
Setting a stage is Pro only.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import auth, classify, config
from ..db import AppStore, get_store, now_utc

router = APIRouter(prefix="/favourites", tags=["favourites"])


class StageBody(BaseModel):
    stage: str = Field(min_length=1, max_length=50)


@router.get("")
def list_favourites(user: dict = Depends(auth.get_current_user),
                    store: AppStore = Depends(get_store)):
    rows = store.fetchall(
        "SELECT tender_id, stage FROM favourites "
        "WHERE user_id = %(user_id)s ORDER BY created_at DESC, id DESC",
        {"user_id": user["id"]})
    now = classify.dhaka_now()
    favourites = []
    for row in rows:
        tender = store.get_tender(row["tender_id"])
        if tender is None:
            continue
        favourites.append({
            "tender_id": row["tender_id"],
            "stage": row["stage"],
            "tender": classify.classify_tender(tender, now=now),
        })
    return {"favourites": favourites,
            "favourite_ids": [f["tender_id"] for f in favourites]}


@router.post("/{tender_id}/toggle")
def toggle_favourite(tender_id: int,
                     user: dict = Depends(auth.get_current_user),
                     store: AppStore = Depends(get_store)):
    if store.get_tender(tender_id) is None:
        raise HTTPException(status_code=404, detail="Tender not found.")
    existing = store.fetchone(
        "SELECT id FROM favourites WHERE user_id = %(user_id)s "
        "AND tender_id = %(tender_id)s",
        {"user_id": user["id"], "tender_id": tender_id})
    if existing is not None:
        store.execute("DELETE FROM favourites WHERE id = %(id)s",
                      {"id": existing["id"]})
        return {"favourite": False}
    plan = auth.get_plan(store, user["id"])
    if config.PLAN_RANK.get(plan, 0) < config.PLAN_RANK["Premium"]:
        count = store.fetchone(
            "SELECT COUNT(*) AS n FROM favourites "
            "WHERE user_id = %(user_id)s", {"user_id": user["id"]})
        if count["n"] >= config.FREE_FAVOURITE_CAP:
            raise HTTPException(status_code=403,
                                detail=auth.FAVOURITE_CAP_ERROR)
    store.insert(
        "INSERT INTO favourites (user_id, tender_id, stage, created_at) "
        "VALUES (%(user_id)s, %(tender_id)s, 'Shortlisted', %(now)s)",
        {"user_id": user["id"], "tender_id": tender_id,
         "now": store.dt(now_utc())})
    return {"favourite": True}


@router.patch("/{tender_id}/stage")
def set_stage(tender_id: int, body: StageBody,
              user: dict = Depends(auth.get_current_user),
              store: AppStore = Depends(get_store)):
    auth.require_plan(store, user, "Pro")
    if body.stage not in config.FAVOURITE_STAGES:
        raise HTTPException(status_code=400, detail="Invalid stage.")
    existing = store.fetchone(
        "SELECT id FROM favourites WHERE user_id = %(user_id)s "
        "AND tender_id = %(tender_id)s",
        {"user_id": user["id"], "tender_id": tender_id})
    if existing is None:
        raise HTTPException(status_code=404, detail="Favourite not found.")
    store.execute(
        "UPDATE favourites SET stage = %(stage)s WHERE id = %(id)s",
        {"stage": body.stage, "id": existing["id"]})
    return {"tender_id": tender_id, "stage": body.stage}
