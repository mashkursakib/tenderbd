"""App database access.

AppStore subclasses the scraper's Store, so tender reads/writes reuse
the verified scraper code (get_tender, upsert_tender, search_tenders,
stats, log_run, tenders_needing_details) and add the app tables from
schema/schema_app.sql (Postgres) or schema/schema_app_sqlite.sql.

SQL is written once with %(name)s placeholders and translated to
SQLite's :name style automatically, following the Store pattern.
Datetimes are stored natively in Postgres, ISO-8601 text in SQLite.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from tenderbd_scraper.config import SETTINGS, Settings
from tenderbd_scraper.db import Store

log = logging.getLogger(__name__)

# Repo root: backend/app/db.py -> parents[2] == tenderbd-production/.
REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO_ROOT / "schema"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_dt(value) -> datetime | None:
    """Parse a stored timestamp (datetime or ISO text) to aware UTC."""
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class AppStore(Store):
    """Store plus the TenderBD app tables."""

    def __init__(self, settings: Settings = SETTINGS) -> None:
        super().__init__(settings)

    # -- schema ---------------------------------------------------------
    def init_app_schema(self) -> None:
        schema_file = ("schema_app.sql" if self.is_postgres
                       else "schema_app_sqlite.sql")
        sql = (SCHEMA_DIR / schema_file).read_text()
        conn = self.connect()
        if self.is_postgres:
            with conn.cursor() as cur:
                cur.execute(sql)
        else:
            conn.executescript(sql)
            conn.commit()
        log.info("App schema initialised (%s)",
                 "PostgreSQL" if self.is_postgres else "SQLite")

    def init_all_schemas(self) -> None:
        self.init_schema()
        self.init_app_schema()

    # -- value helpers --------------------------------------------------
    def dt(self, value: datetime | None):
        """Coerce a datetime for storage on this backend."""
        if value is None:
            return None
        return value if self.is_postgres else value.isoformat()

    def json_in(self, value):
        """Coerce a list/dict for a JSONB (Postgres) / TEXT (SQLite) col."""
        if value is None:
            return None
        if self.is_postgres:
            from psycopg.types.json import Jsonb
            return Jsonb(value)
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def json_out(value):
        """Parse a stored JSON value back to a list/dict."""
        if value is None:
            return None
        if isinstance(value, str):
            try:
                return json.loads(value) if value else None
            except json.JSONDecodeError:
                return None
        return value

    # -- generic helpers ------------------------------------------------
    def fetchone(self, sql: str, params: dict | None = None) -> dict | None:
        cur = self._execute(sql, params)
        row = cur.fetchone()
        return self._row_to_dict(row) if row else None

    def fetchall(self, sql: str, params: dict | None = None) -> list[dict]:
        cur = self._execute(sql, params)
        return [self._row_to_dict(r) for r in cur.fetchall()]

    def execute(self, sql: str, params: dict | None = None) -> None:
        self._execute(sql, params)

    def insert(self, sql: str, params: dict | None = None) -> int:
        """Run an INSERT and return the new row id.

        Postgres uses RETURNING id; SQLite uses cursor.lastrowid.
        """
        conn = self.connect()
        cur = conn.cursor()
        if self.is_postgres:
            cur.execute(sql + " RETURNING id", params or {})
            # Key access, not index access: the Postgres connection
            # uses dict rows, which do not support row[0].
            row_id = cur.fetchone()["id"]
        else:
            cur.execute(self._translate(sql), params or {})
            row_id = cur.lastrowid
            conn.commit()
        return row_id

    # -- tenders (whole-set reads for classification/facets) ------------
    def list_all_tenders(self) -> list[dict]:
        cur = self._execute("SELECT * FROM tenders")
        return [self._row_to_dict(r) for r in cur.fetchall()]

    def last_run(self) -> dict | None:
        return self.fetchone(
            "SELECT * FROM fetch_runs ORDER BY id DESC LIMIT 1")


_store: AppStore | None = None


def get_store() -> AppStore:
    """Process-wide AppStore singleton (built from env on first use)."""
    global _store
    if _store is None:
        _store = AppStore()
    return _store


def reset_store() -> None:
    """Drop the singleton (tests replace it with a temp-DB store)."""
    global _store
    if _store is not None:
        _store.close()
        _store = None


def set_store(store: AppStore | None) -> None:
    """Install a store (tests) or clear it (None)."""
    global _store
    _store = store
