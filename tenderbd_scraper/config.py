"""Configuration for the TenderBD scraper.

Everything is overridable with environment variables (see .env.example).
No credentials of any kind belong here — the scraper only reads public
pages of the e-GP portal, which need no login.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass
class Settings:
    # --- e-GP portal endpoints (public, no login) ---
    base_url: str = "https://eprocure.gov.bd"
    advanced_search_url: str = "https://eprocure.gov.bd/resources/common/AllTenders.jsp?h=t"
    std_search_url: str = "https://eprocure.gov.bd/resources/common/StdTenderSearch.jsp?h=t"
    # The search results are loaded by the portal's own JavaScript through
    # this servlet (POST, funName=AllTenders). Verified live 2026-11-14.
    search_servlet_url: str = "https://eprocure.gov.bd/TenderDetailsServlet"
    notice_url: str = "https://eprocure.gov.bd/resources/common/ViewTender.jsp"
    robots_url: str = "https://eprocure.gov.bd/robots.txt"
    # Official RSS feeds (linked from SubscribeToRSS.jsp). NOTE: as of
    # 2026-11-14 all three returned HTTP 404 ("e-GP Invalid Page") from
    # the live portal, so RSS is treated as a best-effort change signal
    # and the search poll is the reliable path. Re-check periodically.
    rss_feeds: list = field(default_factory=lambda: [
        "https://eprocure.gov.bd/RSS/DailyTender.xml",
        "https://eprocure.gov.bd/RSS/WeeklyTender.xml",
        "https://eprocure.gov.bd/RSS/RSS_eGP.xml",
    ])

    # --- politeness (keep volume close to ordinary human use) ---
    # Identify the project in every request.
    user_agent: str = (
        "TenderBD-Scraper/0.1 (+https://tender.masconsultancy.org; "
        "public e-GP notice aggregator; contact info@masconsultancy.org)"
    )
    request_delay_seconds: float = 2.0   # pause between requests
    request_timeout_seconds: float = 30.0
    max_retries: int = 3                 # exponential backoff: 2s, 4s, 8s
    backoff_base_seconds: float = 2.0

    # --- run limits (guardrails against runaway polling) ---
    search_page_size: int = 10           # portal default; do not raise much
    max_search_pages_per_run: int = 50   # 50 pages x 10 rows = 500 notices
    max_detail_fetches_per_run: int = 100  # notice pages per run
    default_lookback_days: int = 2       # incremental window for `run`

    # --- database ---
    # PostgreSQL when DATABASE_URL is set (Supabase / Neon free tier),
    # otherwise a local SQLite file for development.
    database_url: str = os.environ.get("DATABASE_URL", "")
    sqlite_path: str = os.environ.get("TENDERBD_SQLITE_PATH", "tenderbd.db")

    # --- runtime ---
    log_level: str = os.environ.get("TENDERBD_LOG_LEVEL", "INFO")

    def __post_init__(self) -> None:
        self.request_delay_seconds = _env_float(
            "TENDERBD_REQUEST_DELAY", self.request_delay_seconds)
        self.request_timeout_seconds = _env_float(
            "TENDERBD_REQUEST_TIMEOUT", self.request_timeout_seconds)
        self.max_retries = _env_int("TENDERBD_MAX_RETRIES", self.max_retries)
        self.max_search_pages_per_run = _env_int(
            "TENDERBD_MAX_SEARCH_PAGES", self.max_search_pages_per_run)
        self.max_detail_fetches_per_run = _env_int(
            "TENDERBD_MAX_DETAIL_FETCHES", self.max_detail_fetches_per_run)
        self.default_lookback_days = _env_int(
            "TENDERBD_LOOKBACK_DAYS", self.default_lookback_days)


SETTINGS = Settings()
