"""Explorer classification (SPEC.md section 10).

Backend implements it; the frontend mirrors it for display.
- Work type from proc_nature / proc_type / category.
- Departments by substring on ministry / department / organisation /
  procuring entity (LGED, RHD, BWDB, PWD, BREB).
- Division from a static 64-district table, with aliases
  (Chittagong -> Chattogram, etc.).
- Status buckets vs Asia/Dhaka now: close_dt past -> closed,
  within 7 days -> closing_soon, else active. The Active filter
  matches any non-closed bucket.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .db import parse_dt

DHAKA = ZoneInfo("Asia/Dhaka")

# Static 64-district table: district -> division.
DISTRICT_DIVISION: dict[str, str] = {}
for _division, _districts in {
    "Dhaka": ["Dhaka", "Gazipur", "Narayanganj", "Narsingdi", "Tangail",
              "Kishoreganj", "Manikganj", "Munshiganj", "Rajbari",
              "Madaripur", "Gopalganj", "Faridpur", "Shariatpur"],
    "Chattogram": ["Chattogram", "Cox's Bazar", "Rangamati", "Bandarban",
                   "Khagrachari", "Feni", "Lakshmipur", "Cumilla",
                   "Noakhali", "Brahmanbaria", "Chandpur"],
    "Khulna": ["Khulna", "Bagerhat", "Satkhira", "Jessore", "Jhenaidah",
               "Magura", "Narail", "Chuadanga", "Meherpur", "Kushtia"],
    "Rajshahi": ["Rajshahi", "Chapainawabganj", "Natore", "Naogaon",
                 "Pabna", "Sirajganj", "Bogura", "Joypurhat"],
    "Barishal": ["Barishal", "Bhola", "Patuakhali", "Pirojpur", "Barguna",
                 "Jhalokati"],
    "Sylhet": ["Sylhet", "Moulvibazar", "Habiganj", "Sunamganj"],
    "Rangpur": ["Rangpur", "Dinajpur", "Nilphamari", "Lalmonirhat",
                "Kurigram", "Gaibandha", "Thakurgaon", "Panchagarh"],
    "Mymensingh": ["Mymensingh", "Jamalpur", "Sherpur", "Netrokona"],
}.items():
    for _d in _districts:
        DISTRICT_DIVISION[_d] = _division

# Alternate spellings e-GP / older notices use.
DISTRICT_ALIASES = {
    "chittagong": "Chattogram",
    "chittagong hill tracts": "Chattogram",
    "comilla": "Cumilla",
    "barisal": "Barishal",
    "jashore": "Jessore",
    "jessore": "Jessore",
    "bogra": "Bogura",
    "cox's bazar": "Cox's Bazar",
    "cox bazar": "Cox's Bazar",
    "cox'sbazar": "Cox's Bazar",
    "chapainawabganj": "Chapainawabganj",
    "nawabganj": "Chapainawabganj",
    "chapai nawabganj": "Chapainawabganj",
}


def normalize_district(district: str | None) -> str | None:
    """Canonical district spelling, or None when unknown/empty."""
    if not district:
        return None
    name = " ".join(str(district).strip().split())
    if not name:
        return None
    alias = DISTRICT_ALIASES.get(name.lower())
    if alias:
        return alias
    for canonical in DISTRICT_DIVISION:
        if canonical.lower() == name.lower():
            return canonical
    return name


def division_for_district(district: str | None) -> str | None:
    name = normalize_district(district)
    if name is None:
        return None
    return DISTRICT_DIVISION.get(name)


def classify_work_type(tender: dict) -> str | None:
    """Works / Goods / Services / Consultancy, or None when unstated."""
    text = " ".join([
        str(tender.get("proc_nature") or ""),
        str(tender.get("proc_type") or ""),
        str(tender.get("category") or ""),
    ]).lower()
    if "consult" in text:
        return "Consultancy"
    if "work" in text:
        return "Works"
    if "good" in text:
        return "Goods"
    if "service" in text:
        return "Services"
    return None


DEPARTMENT_KEYWORDS = ["LGED", "RHD", "BWDB", "PWD", "BREB"]


def classify_departments(tender: dict) -> list[str]:
    text = " ".join([
        str(tender.get("ministry") or ""),
        str(tender.get("department") or ""),
        str(tender.get("organisation") or ""),
        str(tender.get("procuring_entity") or ""),
    ]).upper()
    return [dept for dept in DEPARTMENT_KEYWORDS if dept in text]


def dhaka_now() -> datetime:
    return datetime.now(DHAKA)


def status_bucket(tender: dict, now: datetime | None = None) -> str:
    """closed / closing_soon / active vs Asia/Dhaka now."""
    close_dt = parse_dt(tender.get("close_dt"))
    if close_dt is None:
        return "active"
    now = now or dhaka_now()
    if close_dt <= now:
        return "closed"
    if close_dt <= now + timedelta(days=7):
        return "closing_soon"
    return "active"


def is_active_bucket(bucket: str) -> bool:
    """The Active filter matches any non-closed bucket."""
    return bucket in ("active", "closing_soon")


def classify_tender(tender: dict, now: datetime | None = None) -> dict:
    """Attach computed explorer fields to a stored tender row.

    Computed keys never collide with stored columns: the stored
    `division` and `status` columns are left untouched.
    """
    out = dict(tender)
    out["work_type"] = classify_work_type(tender)
    out["departments"] = classify_departments(tender)
    out["computed_division"] = division_for_district(tender.get("district"))
    out["status_bucket"] = status_bucket(tender, now=now)
    return out


def matches_status_filter(bucket: str, statuses: list[str]) -> bool:
    """A status filter matches when any requested bucket matches.

    "active" matches both active and closing_soon buckets.
    """
    wanted = set(statuses)
    if bucket in wanted:
        return True
    if "active" in wanted and is_active_bucket(bucket):
        return True
    return False
