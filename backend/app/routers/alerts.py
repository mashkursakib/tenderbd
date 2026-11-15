"""Alert preferences + matches (SPEC.md section 4).

Reads are NOT plan-gated; saving prefs is Premium+. Matching: AND
across filled groups, substring, max 30 matches from the 300
soonest-closing stored tenders.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from .. import auth, classify
from ..db import AppStore, get_store, now_utc, parse_dt

router = APIRouter(prefix="/alerts", tags=["alerts"])

MATCH_POOL = 300
MATCH_LIMIT = 30


class AlertsBody(BaseModel):
    keywords: str | list[str] | None = None
    categories: str | list[str] | None = None
    districts: str | list[str] | None = None
    organisations: str | list[str] | None = None


def _join(value: str | list[str] | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return ", ".join(part.strip() for part in value if part.strip())


def _split(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip().lower() for part in str(value).split(",")
            if part.strip()]


def _group_matches(values: list[str], haystack: str) -> bool:
    """A group matches when any of its values is a substring."""
    if not values:
        return True
    haystack = haystack.lower()
    return any(value in haystack for value in values)


def find_matches(store: AppStore, prefs: dict | None) -> list[dict]:
    if prefs is None:
        return []
    keywords = _split(prefs.get("keywords"))
    categories = _split(prefs.get("categories"))
    districts = _split(prefs.get("districts"))
    organisations = _split(prefs.get("organisations"))
    if not (keywords or categories or districts or organisations):
        return []
    tenders = store.list_all_tenders()
    tenders.sort(key=lambda t: (parse_dt(t.get("close_dt")) is None,
                               parse_dt(t.get("close_dt")) or
                               parse_dt("9999-12-31")))
    now = classify.dhaka_now()
    matches = []
    for tender in tenders[:MATCH_POOL]:
        keyword_text = " ".join([
            str(tender.get("title") or ""),
            str(tender.get("description") or ""),
            str(tender.get("ref_no") or ""),
            str(tender.get("procuring_entity") or ""),
        ])
        category_text = " ".join([
            str(tender.get("proc_nature") or ""),
            str(tender.get("category") or ""),
        ])
        district_text = str(tender.get("district") or "")
        org_text = " ".join([
            str(tender.get("ministry") or ""),
            str(tender.get("organisation") or ""),
            str(tender.get("department") or ""),
            str(tender.get("procuring_entity") or ""),
        ])
        if not _group_matches(keywords, keyword_text):
            continue
        if not _group_matches(categories, category_text):
            continue
        if not _group_matches(districts, district_text):
            continue
        if not _group_matches(organisations, org_text):
            continue
        matches.append(classify.classify_tender(tender, now=now))
        if len(matches) >= MATCH_LIMIT:
            break
    return matches


def get_prefs(store: AppStore, user_id: int) -> dict | None:
    return store.fetchone(
        "SELECT user_id, keywords, categories, districts, organisations, "
        "updated_at FROM alert_prefs WHERE user_id = %(user_id)s",
        {"user_id": user_id})


@router.get("")
def get_alerts(user: dict = Depends(auth.get_current_user),
               store: AppStore = Depends(get_store)):
    prefs = get_prefs(store, user["id"])
    return {"prefs": prefs, "matches": find_matches(store, prefs)}


@router.put("")
def save_alerts(body: AlertsBody,
                user: dict = Depends(auth.get_current_user),
                store: AppStore = Depends(get_store)):
    auth.require_plan(store, user, "Premium")
    params = {
        "user_id": user["id"],
        "keywords": _join(body.keywords),
        "categories": _join(body.categories),
        "districts": _join(body.districts),
        "organisations": _join(body.organisations),
        "updated_at": store.dt(now_utc()),
    }
    store.execute(
        "INSERT INTO alert_prefs (user_id, keywords, categories, "
        "districts, organisations, updated_at) "
        "VALUES (%(user_id)s, %(keywords)s, %(categories)s, "
        "%(districts)s, %(organisations)s, %(updated_at)s) "
        "ON CONFLICT (user_id) DO UPDATE SET "
        "keywords = EXCLUDED.keywords, "
        "categories = EXCLUDED.categories, "
        "districts = EXCLUDED.districts, "
        "organisations = EXCLUDED.organisations, "
        "updated_at = EXCLUDED.updated_at",
        params)
    return get_prefs(store, user["id"])
