"""Company profile (SPEC.md section 4). Saving is NOT plan-gated."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from .. import auth
from ..db import AppStore, get_store, now_utc

router = APIRouter(prefix="/profile", tags=["profile"])

MAX_SIMILAR_WORKS = 30


class SimilarWork(BaseModel):
    title: str = Field(max_length=300)
    value_bdt: int | None = Field(default=None, ge=0)
    category: str | None = Field(default=None, max_length=200)


class CompanyBody(BaseModel):
    company_name: str = Field(min_length=1, max_length=300)
    trade_license_no: str | None = Field(default=None, max_length=200)
    tin_no: str | None = Field(default=None, max_length=200)
    incorporation_year: int | None = Field(default=None, ge=1900, le=2100)
    annual_turnover_bdt: int | None = Field(default=None, ge=0)
    liquid_assets_bdt: int | None = Field(default=None, ge=0)
    categories: str | list[str] | None = None
    districts: str | list[str] | None = None
    similar_works: list[SimilarWork] | None = Field(
        default=None, max_length=MAX_SIMILAR_WORKS)
    key_personnel: str | None = Field(default=None, max_length=5000)
    equipment: str | None = Field(default=None, max_length=5000)
    about: str | None = Field(default=None, max_length=5000)


def _join(value: str | list[str] | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return ", ".join(part.strip() for part in value if part.strip())


def serialize_company(row: dict | None, store: AppStore) -> dict | None:
    if row is None:
        return None
    out = dict(row)
    out["similar_works"] = store.json_out(row.get("similar_works")) or []
    return out


def get_company_profile(store: AppStore, user_id: int) -> dict | None:
    row = store.fetchone(
        "SELECT * FROM companies WHERE user_id = %(user_id)s",
        {"user_id": user_id})
    return serialize_company(row, store)


@router.get("/company")
def get_company(user: dict = Depends(auth.get_current_user),
                store: AppStore = Depends(get_store)):
    return get_company_profile(store, user["id"])


@router.put("/company")
def save_company(body: CompanyBody,
                 user: dict = Depends(auth.get_current_user),
                 store: AppStore = Depends(get_store)):
    now = now_utc()
    works = [w.model_dump() for w in (body.similar_works or [])]
    params = {
        "user_id": user["id"],
        "company_name": body.company_name.strip(),
        "trade_license_no": body.trade_license_no,
        "tin_no": body.tin_no,
        "incorporation_year": body.incorporation_year,
        "annual_turnover_bdt": body.annual_turnover_bdt,
        "liquid_assets_bdt": body.liquid_assets_bdt,
        "categories": _join(body.categories),
        "districts": _join(body.districts),
        "similar_works": store.json_in(works),
        "key_personnel": body.key_personnel,
        "equipment": body.equipment,
        "about": body.about,
        "updated_at": store.dt(now),
    }
    store.execute(
        "INSERT INTO companies (user_id, company_name, trade_license_no, "
        "tin_no, incorporation_year, annual_turnover_bdt, "
        "liquid_assets_bdt, categories, districts, similar_works, "
        "key_personnel, equipment, about, updated_at) "
        "VALUES (%(user_id)s, %(company_name)s, %(trade_license_no)s, "
        "%(tin_no)s, %(incorporation_year)s, %(annual_turnover_bdt)s, "
        "%(liquid_assets_bdt)s, %(categories)s, %(districts)s, "
        "%(similar_works)s, %(key_personnel)s, %(equipment)s, "
        "%(about)s, %(updated_at)s) "
        "ON CONFLICT (user_id) DO UPDATE SET "
        "company_name = EXCLUDED.company_name, "
        "trade_license_no = EXCLUDED.trade_license_no, "
        "tin_no = EXCLUDED.tin_no, "
        "incorporation_year = EXCLUDED.incorporation_year, "
        "annual_turnover_bdt = EXCLUDED.annual_turnover_bdt, "
        "liquid_assets_bdt = EXCLUDED.liquid_assets_bdt, "
        "categories = EXCLUDED.categories, "
        "districts = EXCLUDED.districts, "
        "similar_works = EXCLUDED.similar_works, "
        "key_personnel = EXCLUDED.key_personnel, "
        "equipment = EXCLUDED.equipment, "
        "about = EXCLUDED.about, "
        "updated_at = EXCLUDED.updated_at",
        params)
    return get_company_profile(store, user["id"])
