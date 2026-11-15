"""Tender explorer, detail, evaluate, summarize, refresh
(SPEC.md sections 4, 7, 8, 10, 11)."""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field
from tenderbd_scraper.http import FetchError

from .. import auth, classify, config
from ..db import AppStore, get_store, parse_dt
from ..services import eligibility, refresh as refresh_service
from ..services import summarize as summarize_service
from .profile import get_company_profile

log = logging.getLogger(__name__)

router = APIRouter(tags=["tenders"])

SORTS = {"closing", "published", "newest_id", "value_high", "value_low"}


class RefreshBody(BaseModel):
    days: int = Field(default=3, ge=1, le=30)
    max_pages: int = Field(default=5, ge=1, le=50)
    enrich_limit: int = Field(default=12, ge=0, le=100)


class SummarizeBody(BaseModel):
    lang: str = Field(default="en", pattern="^(en|bn)$")


# -- helpers -------------------------------------------------------------
def _sort_with_nulls_last(rows, keyfn, reverse=False):
    dated = [r for r in rows if keyfn(r) is not None]
    undated = [r for r in rows if keyfn(r) is None]
    dated.sort(key=keyfn, reverse=reverse)
    return dated + undated


def _apply_sort(rows: list[dict], sort: str) -> list[dict]:
    if sort == "published":
        return _sort_with_nulls_last(
            rows, lambda r: parse_dt(r.get("publish_dt")), reverse=True)
    if sort == "newest_id":
        return sorted(rows, key=lambda r: r["tender_id"], reverse=True)
    if sort == "value_high":
        return _sort_with_nulls_last(
            rows, lambda r: r.get("emd_bdt"), reverse=True)
    if sort == "value_low":
        return _sort_with_nulls_last(rows, lambda r: r.get("emd_bdt"))
    return _sort_with_nulls_last(rows, lambda r: parse_dt(r.get("close_dt")))


def _merge_params(bracketed, plain) -> list[str]:
    values = []
    for source in (bracketed, plain):
        if source:
            values.extend(source)
    return values


def _get_tender_or_404(store: AppStore, tender_id: int) -> dict:
    tender = store.get_tender(tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail="Tender not found.")
    return tender


def _maybe_enrich(store: AppStore, tender: dict) -> dict:
    """Enrich from the public e-GP notice page on first open.

    If the live fetch fails, the stored row is returned unchanged.
    """
    if tender.get("detail_fetched_at") is not None:
        return tender
    try:
        enriched = refresh_service.enrich_tender(store, tender["tender_id"])
        if enriched is not None:
            return enriched
    except Exception as exc:  # noqa: BLE001 - enrich is best-effort
        log.warning("Enrichment failed for tender %s: %s",
                    tender["tender_id"], exc)
    return tender


# -- list ----------------------------------------------------------------
@router.get("/tenders")
def list_tenders(
    q: str | None = Query(default=None, max_length=200),
    work_types: list[str] | None = Query(default=None,
                                         alias="work_types[]"),
    work_types_plain: list[str] | None = Query(default=None,
                                               alias="work_types"),
    departments: list[str] | None = Query(default=None,
                                          alias="departments[]"),
    departments_plain: list[str] | None = Query(default=None,
                                                alias="departments"),
    division: str | None = Query(default=None, max_length=100),
    district: str | None = Query(default=None, max_length=100),
    value_min: int | None = Query(default=None, ge=0),
    value_max: int | None = Query(default=None, ge=0),
    statuses: list[str] | None = Query(default=None, alias="statuses[]"),
    statuses_plain: list[str] | None = Query(default=None,
                                             alias="statuses"),
    method: str | None = Query(default=None, max_length=100),
    sort: str = Query(default="closing"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    store: AppStore = Depends(get_store),
):
    if sort not in SORTS:
        raise HTTPException(status_code=400,
                            detail=f"Unknown sort: {sort}.")
    wanted_work_types = set(_merge_params(work_types, work_types_plain))
    wanted_departments = set(_merge_params(departments, departments_plain))
    wanted_statuses = _merge_params(statuses, statuses_plain)
    wanted_district = classify.normalize_district(district)
    now = classify.dhaka_now()

    classified = [classify.classify_tender(t, now=now)
                  for t in store.list_all_tenders()]

    # Facets over the whole stored set.
    work_type_counts: dict[str, int] = {}
    department_counts: dict[str, int] = {}
    districts: set[str] = set()
    divisions: set[str] = set()
    methods: set[str] = set()
    for tender in classified:
        work_type = tender.get("work_type")
        if work_type:
            work_type_counts[work_type] = work_type_counts.get(work_type, 0) + 1
        for dept in tender.get("departments") or []:
            department_counts[dept] = department_counts.get(dept, 0) + 1
        if tender.get("district"):
            districts.add(str(tender["district"]))
        if tender.get("computed_division"):
            divisions.add(tender["computed_division"])
        if tender.get("method"):
            methods.add(str(tender["method"]))

    # Filters.
    query = (q or "").strip().lower()
    filtered = []
    for tender in classified:
        if query:
            haystack = " ".join([
                str(tender.get("title") or ""),
                str(tender.get("ref_no") or ""),
                str(tender.get("procuring_entity") or ""),
                str(tender.get("tender_id")),
            ]).lower()
            if query not in haystack:
                continue
        if wanted_work_types and tender.get("work_type") not in wanted_work_types:
            continue
        if wanted_departments and not (
                set(tender.get("departments") or []) & wanted_departments):
            continue
        if division and tender.get("computed_division") != division:
            continue
        if wanted_district and classify.normalize_district(
                tender.get("district")) != wanted_district:
            continue
        emd = tender.get("emd_bdt")
        if value_min is not None and (emd is None or emd < value_min):
            continue
        if value_max is not None and (emd is None or emd > value_max):
            continue
        if wanted_statuses and not classify.matches_status_filter(
                tender["status_bucket"], wanted_statuses):
            continue
        if method and tender.get("method") != method:
            continue
        filtered.append(tender)

    total = len(filtered)
    page = _apply_sort(filtered, sort)[offset:offset + limit]
    return {
        "tenders": page,
        "total": total,
        "work_type_counts": work_type_counts,
        "department_counts": department_counts,
        "districts": sorted(districts),
        "divisions": sorted(divisions),
        "methods": sorted(methods),
    }


# -- detail --------------------------------------------------------------
@router.get("/tenders/{tender_id}")
def get_tender(tender_id: int, store: AppStore = Depends(get_store)):
    tender = _get_tender_or_404(store, tender_id)
    tender = _maybe_enrich(store, tender)
    return classify.classify_tender(tender)


# -- evaluate / summarize (Premium+) --------------------------------------
@router.post("/tenders/{tender_id}/evaluate")
def evaluate_tender(tender_id: int,
                    user: dict = Depends(auth.get_current_user),
                    store: AppStore = Depends(get_store)):
    auth.require_plan(store, user, "Premium")
    tender = _get_tender_or_404(store, tender_id)
    profile = get_company_profile(store, user["id"])
    return eligibility.evaluate(tender, profile)


@router.post("/tenders/{tender_id}/summarize")
def summarize_tender(tender_id: int, body: SummarizeBody,
                     user: dict = Depends(auth.get_current_user),
                     store: AppStore = Depends(get_store)):
    auth.require_plan(store, user, "Premium")
    tender = _get_tender_or_404(store, tender_id)
    tender = _maybe_enrich(store, tender)
    if not summarize_service.has_enough_text(tender):
        raise HTTPException(
            status_code=400,
            detail=summarize_service.TOO_LITTLE_TEXT_ERROR)
    return summarize_service.summarize(tender, lang=body.lang)


# -- refresh --------------------------------------------------------------
@router.post("/refresh")
def refresh(body: RefreshBody,
            request: Request,
            x_refresh_token: str | None = Header(default=None),
            store: AppStore = Depends(get_store)):
    # Authorized two ways: the shared refresh token (scheduled jobs)
    # or a signed-in admin session (the Refresh button in the UI,
    # which cannot carry the shared token). An admin session works
    # even when no refresh token is configured.
    user = auth.get_optional_user(request, store)
    if user is None or not user.get("is_admin"):
        expected = config.refresh_token()
        if not expected:
            raise HTTPException(status_code=503,
                                detail="Refresh is not configured.")
        if x_refresh_token != expected:
            raise HTTPException(status_code=403,
                                detail="Invalid refresh token.")
    try:
        summary = refresh_service.run_refresh(
            store, days=body.days, max_pages=body.max_pages,
            enrich_limit=body.enrich_limit)
    except FetchError:
        raise HTTPException(
            status_code=502,
            detail="The e-GP portal could not be reached. "
                   "Try again later.")
    return summary
