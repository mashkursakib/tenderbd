"""AppStore tests — PostgreSQL backend.

Skipped unless TENDERBD_TEST_DATABASE_URL is set. Point it at a
THROWAWAY database: the tests TRUNCATE all app tables in it.

    TENDERBD_TEST_DATABASE_URL=postgresql://user:pass@host:5432/db \\
        pytest backend/tests/test_db_postgres.py

These tests exist because the Postgres branch of AppStore was never
live-tested until the coordinator's integration pass: insert()
used index access on a dict row (cur.fetchone()[0]), which raised
KeyError on Postgres and broke every signup on the Postgres backend
until fixed (2026-11-15).
"""

import os
from datetime import datetime, timezone

import pytest

from backend.app.db import AppStore, parse_dt
from tenderbd_scraper.config import Settings

PG_URL = os.environ.get("TENDERBD_TEST_DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not PG_URL, reason="TENDERBD_TEST_DATABASE_URL not set")

TABLES = ("users, sign_in_attempts, subscriptions, companies, "
          "documents, favourites, alert_prefs, jv_posts, "
          "jv_interests, jv_rooms, jv_messages, payment_submissions, "
          "consulting_requests, tenders, fetch_runs")


@pytest.fixture()
def store():
    settings = Settings()
    settings.database_url = PG_URL
    s = AppStore(settings)
    assert s.is_postgres
    s.init_all_schemas()
    s._execute(f"TRUNCATE {TABLES}")
    yield s
    s._execute(f"TRUNCATE {TABLES}")
    s.close()


def test_insert_returns_id_and_row_reads_back(store):
    """Regression: RETURNING id on a dict-row connection."""
    user_id = store.insert(
        "INSERT INTO users (email, password_hash, name) "
        "VALUES (%(email)s, %(hash)s, %(name)s)",
        {"email": "pg@example.com", "hash": "argon2id-hash",
         "name": "PG User"})
    assert isinstance(user_id, int) and user_id > 0
    row = store.fetchone("SELECT * FROM users WHERE id = %(id)s",
                         {"id": user_id})
    assert row["email"] == "pg@example.com"
    assert row["is_admin"] is False


def test_jsonb_round_trip(store):
    user_id = store.insert(
        "INSERT INTO users (email, password_hash, name) "
        "VALUES (%(email)s, %(hash)s, %(name)s)",
        {"email": "co@example.com", "hash": "h", "name": "Co"})
    works = [{"title": "School building", "value_bdt": 3000000,
              "category": "Works"}]
    store.insert(
        "INSERT INTO companies (user_id, company_name, similar_works) "
        "VALUES (%(user_id)s, %(name)s, %(works)s)",
        {"user_id": user_id, "name": "PG Builders Ltd",
         "works": store.json_in(works)})
    row = store.fetchone(
        "SELECT * FROM companies WHERE user_id = %(user_id)s",
        {"user_id": user_id})
    assert store.json_out(row["similar_works"]) == works


def test_bytea_round_trip(store):
    user_id = store.insert(
        "INSERT INTO users (email, password_hash, name) "
        "VALUES (%(email)s, %(hash)s, %(name)s)",
        {"email": "doc@example.com", "hash": "h", "name": "Doc"})
    blob = b"TRADE LICENCE BYTES \x00\x01\x02"
    doc_id = store.insert(
        "INSERT INTO documents (user_id, doc_type, file_name, "
        "mime_type, size_bytes, data) "
        "VALUES (%(user_id)s, %(doc_type)s, %(file_name)s, "
        "%(mime_type)s, %(size)s, %(data)s)",
        {"user_id": user_id, "doc_type": "Trade licence",
         "file_name": "licence.bin", "mime_type": "application/octet-stream",
         "size": len(blob), "data": blob})
    row = store.fetchone("SELECT * FROM documents WHERE id = %(id)s",
                         {"id": doc_id})
    assert bytes(row["data"]) == blob


def test_timestamptz_round_trip(store):
    expires = datetime(2026, 12, 15, 10, 30, tzinfo=timezone.utc)
    user_id = store.insert(
        "INSERT INTO users (email, password_hash, name, "
        "session_token, session_expires_at) "
        "VALUES (%(email)s, %(hash)s, %(name)s, %(token)s, %(expires)s)",
        {"email": "ts@example.com", "hash": "h", "name": "TS",
         "token": "a" * 48, "expires": store.dt(expires)})
    row = store.fetchone("SELECT * FROM users WHERE id = %(id)s",
                         {"id": user_id})
    assert parse_dt(row["session_expires_at"]) == expires
