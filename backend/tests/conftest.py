"""Shared fixtures for the TenderBD backend tests.

Tests run against a temp-file SQLite DB; the live e-GP portal is never
hit (fetcher calls are monkeypatched where a test needs them).
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tenderbd_scraper.config import Settings  # noqa: E402
from backend.app import db as db_module  # noqa: E402
from backend.app.db import AppStore  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.tests.helpers import (ADMIN_EMAIL, REFRESH_TOKEN,  # noqa: E402
                                   seed_tenders)


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", ADMIN_EMAIL)
    monkeypatch.setenv("REFRESH_TOKEN", REFRESH_TOKEN)
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    settings = Settings()
    settings.database_url = ""
    settings.sqlite_path = str(tmp_path / "test.db")
    s = AppStore(settings)
    s.init_all_schemas()
    seed_tenders(s)
    db_module.set_store(s)
    yield s
    db_module.set_store(None)
    s.close()


@pytest.fixture()
def client(store):
    with TestClient(app) as c:
        yield c
