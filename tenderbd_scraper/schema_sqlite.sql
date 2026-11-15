-- TenderBD schema — SQLite fallback for local development.
-- Same columns as schema.sql; datetimes stored as ISO-8601 text,
-- JSON stored as text. The Store class translates automatically.

CREATE TABLE IF NOT EXISTS tenders (
    tender_id            INTEGER PRIMARY KEY,
    ref_no               TEXT,
    app_id               INTEGER,
    title                TEXT,
    description          TEXT,
    status               TEXT,
    proc_nature          TEXT,
    proc_type            TEXT,
    event_type           TEXT,
    invitation_for       TEXT,
    method               TEXT,
    budget_type          TEXT,
    source_of_funds      TEXT,
    ministry             TEXT,
    division             TEXT,
    organisation         TEXT,
    department           TEXT,
    procuring_entity     TEXT,
    procuring_entity_code TEXT,
    district             TEXT,
    project_code         TEXT,
    project_name         TEXT,
    package_no           TEXT,
    package_description  TEXT,
    category             TEXT,
    publish_dt           TEXT,
    doc_last_selling_dt  TEXT,
    pre_tender_meeting_start TEXT,
    pre_tender_meeting_end   TEXT,
    close_dt             TEXT,
    opening_dt           TEXT,
    security_submission_dt   TEXT,
    security_valid_up_to TEXT,
    tender_valid_up_to   TEXT,
    document_price_bdt   INTEGER,
    emd_bdt              INTEGER,
    evaluation_type      TEXT,
    document_available   TEXT,
    document_fees        TEXT,
    payment_mode         TEXT,
    eligibility_text     TEXT,
    lots                 TEXT,
    corrigendum_text     TEXT,
    source_url           TEXT,
    first_seen_at        TEXT NOT NULL,
    last_seen_at         TEXT NOT NULL,
    detail_fetched_at    TEXT
);

CREATE INDEX IF NOT EXISTS idx_tenders_close_dt    ON tenders (close_dt);
CREATE INDEX IF NOT EXISTS idx_tenders_publish_dt  ON tenders (publish_dt);
CREATE INDEX IF NOT EXISTS idx_tenders_ministry    ON tenders (ministry);
CREATE INDEX IF NOT EXISTS idx_tenders_district    ON tenders (district);
CREATE INDEX IF NOT EXISTS idx_tenders_method      ON tenders (method);
CREATE INDEX IF NOT EXISTS idx_tenders_nature      ON tenders (proc_nature);
CREATE INDEX IF NOT EXISTS idx_tenders_status      ON tenders (status);

CREATE TABLE IF NOT EXISTS fetch_runs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at       TEXT NOT NULL,
    finished_at      TEXT,
    source           TEXT NOT NULL,
    tenders_found    INTEGER NOT NULL DEFAULT 0,
    tenders_new      INTEGER NOT NULL DEFAULT 0,
    tenders_updated  INTEGER NOT NULL DEFAULT 0,
    details_fetched  INTEGER NOT NULL DEFAULT 0,
    errors           INTEGER NOT NULL DEFAULT 0,
    notes            TEXT
);
