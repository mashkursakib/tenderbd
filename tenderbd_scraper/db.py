"""Storage for TenderBD — PostgreSQL when DATABASE_URL is set, else SQLite.

One Store class works for both backends:
- SQL is written once with %(name)s placeholders and translated to
  SQLite's :name style automatically.
- Datetimes are stored natively in Postgres, ISO-8601 text in SQLite.
- JSON (lots) is stored as a JSON string in both.

Dedupe is by Tender ID: upsert_tender() inserts a new row or updates
the existing one, preserving first_seen_at.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .config import SETTINGS

log = logging.getLogger(__name__)

# Columns that may be upserted (tender_id is the key).
COLUMNS = [
    "ref_no", "app_id", "title", "description", "status",
    "proc_nature", "proc_type", "event_type", "invitation_for",
    "method", "budget_type", "source_of_funds",
    "ministry", "division", "organisation", "department",
    "procuring_entity", "procuring_entity_code", "district",
    "project_code", "project_name", "package_no", "package_description",
    "category",
    "publish_dt", "doc_last_selling_dt", "pre_tender_meeting_start",
    "pre_tender_meeting_end", "close_dt", "opening_dt",
    "security_submission_dt", "security_valid_up_to", "tender_valid_up_to",
    "document_price_bdt", "emd_bdt",
    "evaluation_type", "document_available", "document_fees",
    "payment_mode", "eligibility_text", "lots", "corrigendum_text",
    "source_url",
]

_DATETIME_COLUMNS = {
    "publish_dt", "doc_last_selling_dt", "pre_tender_meeting_start",
    "pre_tender_meeting_end", "close_dt", "opening_dt",
    "security_submission_dt", "security_valid_up_to", "tender_valid_up_to",
}

_PLACEHOLDER_RE = re.compile(r"%\((\w+)\)s")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Store:
    def __init__(self, settings: Settings = SETTINGS) -> None:
        self.settings = settings
        self.is_postgres = bool(settings.database_url)
        self._conn = None

    # -- connection -----------------------------------------------------
    def connect(self):
        if self._conn is not None:
            return self._conn
        if self.is_postgres:
            import psycopg
            from psycopg.rows import dict_row
            self._conn = psycopg.connect(self.settings.database_url,
                                         autocommit=True,
                                         row_factory=dict_row)
            log.info("Connected to PostgreSQL")
        else:
            path = Path(self.settings.sqlite_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            # check_same_thread=False: the FastAPI app serves requests
            # from worker threads sharing this connection.
            self._conn = sqlite3.connect(str(path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            log.info("Using SQLite database at %s", path)
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _translate(self, sql: str) -> str:
        if self.is_postgres:
            return sql
        return _PLACEHOLDER_RE.sub(r":\1", sql)

    def _execute(self, sql: str, params: dict | None = None):
        conn = self.connect()
        cur = conn.cursor()
        cur.execute(self._translate(sql), params or {})
        if not self.is_postgres:
            conn.commit()
        return cur

    # -- schema ---------------------------------------------------------
    def init_schema(self) -> None:
        schema_file = ("schema.sql" if self.is_postgres
                       else "schema_sqlite.sql")
        sql = (Path(__file__).parent / schema_file).read_text()
        conn = self.connect()
        if self.is_postgres:
            with conn.cursor() as cur:
                cur.execute(sql)
        else:
            conn.executescript(sql)
            conn.commit()
        log.info("Schema initialised (%s)",
                 "PostgreSQL" if self.is_postgres else "SQLite")

    # -- values ---------------------------------------------------------
    def _coerce(self, column: str, value):
        if value is None:
            return None
        if column == "lots" and not isinstance(value, str):
            return json.dumps(value, ensure_ascii=False)
        if column in _DATETIME_COLUMNS and isinstance(value, datetime):
            return value if self.is_postgres else value.isoformat()
        return value

    # -- tenders --------------------------------------------------------
    def upsert_tender(self, record: dict, *, detail_fetched: bool = False) -> str:
        """Insert or update one tender. Returns 'new' or 'updated'."""
        tender_id = record["tender_id"]
        existing = self.get_tender(tender_id)
        now = _now()
        data = {"tender_id": tender_id}
        for col in COLUMNS:
            if col in record:
                data[col] = self._coerce(col, record[col])
        data["last_seen_at"] = now if self.is_postgres else now.isoformat()
        # first_seen_at must be present in every proposed row: NOT NULL is
        # checked before ON CONFLICT handling. It is excluded from the
        # UPDATE assignments, so existing rows keep their original value.
        data["first_seen_at"] = data["last_seen_at"]
        if detail_fetched:
            data["detail_fetched_at"] = data["last_seen_at"]
        cols = list(data.keys())
        placeholders = ", ".join(f"%({c})s" for c in cols)
        update_cols = [c for c in cols
                       if c not in ("tender_id", "first_seen_at")]
        assignments = ", ".join(
            f"{c} = EXCLUDED.{c}" for c in update_cols)
        sql = (f"INSERT INTO tenders ({', '.join(cols)}) "
               f"VALUES ({placeholders}) "
               f"ON CONFLICT (tender_id) DO UPDATE SET {assignments}")
        self._execute(sql, data)
        return "new" if existing is None else "updated"

    def get_tender(self, tender_id: int) -> dict | None:
        cur = self._execute(
            "SELECT * FROM tenders WHERE tender_id = %(tender_id)s",
            {"tender_id": tender_id})
        row = cur.fetchone()
        return self._row_to_dict(row) if row else None

    def tender_exists(self, tender_id: int) -> bool:
        return self.get_tender(tender_id) is not None

    def tenders_needing_details(self, limit: int) -> list[int]:
        """Tender ids without a fetched notice page, newest first.

        Used by the enrichment step so tenders skipped by a previous
        run's cap are picked up by later runs instead of staying
        un-enriched forever.
        """
        cur = self._execute(
            "SELECT tender_id FROM tenders "
            "WHERE detail_fetched_at IS NULL "
            "ORDER BY publish_dt DESC NULLS LAST, tender_id DESC "
            "LIMIT %(limit)s",
            {"limit": limit})
        # Key access, not index access: the Postgres connection uses
        # dict rows, which do not support row[0].
        return [row["tender_id"] for row in cur.fetchall()]

    def search_tenders(self, *, query: str | None = None,
                       ministry: str | None = None,
                       district: str | None = None,
                       method: str | None = None,
                       proc_nature: str | None = None,
                       status: str | None = None,
                       closing_before: datetime | None = None,
                       closing_after: datetime | None = None,
                       sort: str = "close_dt",
                       limit: int = 20, offset: int = 0) -> tuple[list[dict], int]:
        """Filtered tender search for the API. Returns (rows, total)."""
        where = ["1=1"]
        params: dict = {}
        if query:
            where.append("(title ILIKE %(q)s OR ref_no ILIKE %(q)s "
                         "OR procuring_entity ILIKE %(q)s"
                         " OR CAST(tender_id AS TEXT) LIKE %(q)s)")
            if not self.is_postgres:
                where[-1] = where[-1].replace("ILIKE", "LIKE")
            params["q"] = f"%{query}%"
        for col, val in (("ministry", ministry), ("district", district),
                         ("method", method), ("proc_nature", proc_nature),
                         ("status", status)):
            if val:
                where.append(f"{col} = %({col})s")
                params[col] = val
        if closing_before:
            where.append("close_dt <= %(closing_before)s")
            params["closing_before"] = (closing_before if self.is_postgres
                                        else closing_before.isoformat())
        if closing_after:
            where.append("close_dt >= %(closing_after)s")
            params["closing_after"] = (closing_after if self.is_postgres
                                       else closing_after.isoformat())
        where_sql = " AND ".join(where)
        sort_col = sort if sort in ("close_dt", "publish_dt", "tender_id") \
            else "close_dt"
        count_cur = self._execute(
            f"SELECT COUNT(*) AS total FROM tenders WHERE {where_sql}",
            params)
        total = count_cur.fetchone()["total"]
        params["limit"] = limit
        params["offset"] = offset
        cur = self._execute(
            f"SELECT * FROM tenders WHERE {where_sql} "
            f"ORDER BY {sort_col} ASC LIMIT %(limit)s OFFSET %(offset)s",
            params)
        return [self._row_to_dict(r) for r in cur.fetchall()], total

    def stats(self) -> dict:
        cur = self._execute(
            "SELECT COUNT(*) AS total, "
            "COUNT(*) FILTER (WHERE close_dt >= NOW()) AS open_now "
            "FROM tenders" if self.is_postgres else
            "SELECT COUNT(*) AS total, "
            "COUNT(CASE WHEN close_dt >= datetime('now') THEN 1 END) "
            "AS open_now FROM tenders")
        row = cur.fetchone()
        total, open_now = row["total"], row["open_now"]
        cur = self._execute(
            "SELECT MAX(last_seen_at) AS last_seen FROM tenders")
        last_seen = cur.fetchone()["last_seen"]
        return {"total_tenders": total, "open_tenders": open_now,
                "last_seen_at": str(last_seen) if last_seen else None}

    def _row_to_dict(self, row) -> dict:
        """Normalise a DB row to a JSON-ready dict.

        Datetimes become ISO-8601 strings and the lots JSON string
        becomes a list, identically on both backends.
        """
        out = dict(row)
        for col in list(out.keys()):
            value = out[col]
            if isinstance(value, datetime):
                out[col] = value.isoformat()
            elif col == "lots" and isinstance(value, str):
                try:
                    out[col] = json.loads(value) if value else []
                except json.JSONDecodeError:
                    out[col] = []
        return out

    # -- run log --------------------------------------------------------
    def log_run(self, *, source: str, tenders_found: int = 0,
                tenders_new: int = 0, tenders_updated: int = 0,
                details_fetched: int = 0, errors: int = 0,
                notes: str = "") -> None:
        now = _now()
        now_val = now if self.is_postgres else now.isoformat()
        self._execute(
            "INSERT INTO fetch_runs (started_at, finished_at, source, "
            "tenders_found, tenders_new, tenders_updated, "
            "details_fetched, errors, notes) "
            "VALUES (%(started_at)s, %(finished_at)s, %(source)s, "
            "%(tenders_found)s, %(tenders_new)s, %(tenders_updated)s, "
            "%(details_fetched)s, %(errors)s, %(notes)s)",
            {"started_at": now_val, "finished_at": now_val,
             "source": source, "tenders_found": tenders_found,
             "tenders_new": tenders_new, "tenders_updated": tenders_updated,
             "details_fetched": details_fetched, "errors": errors,
             "notes": notes})
