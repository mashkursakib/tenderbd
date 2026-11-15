"""Backend configuration, read from the environment.

Values are read lazily (per call) so tests can override them with
monkeypatch.setenv without reimporting. See SPEC.md section 12.
"""

from __future__ import annotations

import os

DEFAULT_ADMIN_EMAILS = (
    "mashkursakib@gmail.com,info@masconsultancy.org,"
    "masconsultancybd@gmail.com"
)

PLAN_RANK = {"Free": 0, "Premium": 1, "Pro": 2}
PLAN_PRICES_BDT = {"Premium": 399, "Pro": 799}
FREE_FAVOURITE_CAP = 3
MAX_DOCUMENT_BYTES = 6 * 1024 * 1024

DOC_TYPES = [
    "Trade licence",
    "TIN / VAT certificate",
    "Certificate of incorporation",
    "Audited financial statements",
    "Bank solvency / credit line letter",
    "Work completion certificate",
    "Key personnel CVs",
    "Equipment list",
    "Other",
]

FAVOURITE_STAGES = ["Watching", "Shortlisted", "Preparing",
                    "Submitted", "Won", "Lost"]

WORK_TYPES = ["Works", "Goods", "Services", "Consultancy"]
DEPARTMENTS = ["LGED", "RHD", "BWDB", "PWD", "BREB"]


def admin_emails() -> set[str]:
    raw = os.environ.get("ADMIN_EMAILS", DEFAULT_ADMIN_EMAILS)
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def refresh_token() -> str:
    return os.environ.get("REFRESH_TOKEN", "")


def resend_api_key() -> str:
    return os.environ.get("RESEND_API_KEY", "")


def resend_from() -> str:
    return os.environ.get("RESEND_FROM", "TenderBD <onboarding@resend.dev>")


def app_base_url() -> str:
    return os.environ.get(
        "APP_BASE_URL", "https://tender.masconsultancy.org").rstrip("/")
