-- TenderBD schema — PostgreSQL (Supabase / Neon free tier).
-- Dedupe key is the e-GP Tender/Proposal ID.

CREATE TABLE IF NOT EXISTS tenders (
    tender_id            BIGINT PRIMARY KEY,
    ref_no               TEXT,
    app_id               BIGINT,
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
    publish_dt           TIMESTAMPTZ,
    doc_last_selling_dt  TIMESTAMPTZ,
    pre_tender_meeting_start TIMESTAMPTZ,
    pre_tender_meeting_end   TIMESTAMPTZ,
    close_dt             TIMESTAMPTZ,
    opening_dt           TIMESTAMPTZ,
    security_submission_dt   TIMESTAMPTZ,
    security_valid_up_to TIMESTAMPTZ,
    tender_valid_up_to   TIMESTAMPTZ,
    document_price_bdt   INTEGER,
    emd_bdt              INTEGER,
    evaluation_type      TEXT,
    document_available   TEXT,
    document_fees        TEXT,
    payment_mode         TEXT,
    eligibility_text     TEXT,
    lots                 JSONB,
    corrigendum_text     TEXT,
    source_url           TEXT,
    first_seen_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    detail_fetched_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_tenders_close_dt    ON tenders (close_dt);
CREATE INDEX IF NOT EXISTS idx_tenders_publish_dt  ON tenders (publish_dt);
CREATE INDEX IF NOT EXISTS idx_tenders_ministry    ON tenders (ministry);
CREATE INDEX IF NOT EXISTS idx_tenders_district    ON tenders (district);
CREATE INDEX IF NOT EXISTS idx_tenders_method      ON tenders (method);
CREATE INDEX IF NOT EXISTS idx_tenders_nature      ON tenders (proc_nature);
CREATE INDEX IF NOT EXISTS idx_tenders_status      ON tenders (status);

-- Run log: one row per scraper run, for monitoring and debugging.
CREATE TABLE IF NOT EXISTS fetch_runs (
    id               SERIAL PRIMARY KEY,
    started_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at      TIMESTAMPTZ,
    source           TEXT NOT NULL,
    tenders_found    INTEGER NOT NULL DEFAULT 0,
    tenders_new      INTEGER NOT NULL DEFAULT 0,
    tenders_updated  INTEGER NOT NULL DEFAULT 0,
    details_fetched  INTEGER NOT NULL DEFAULT 0,
    errors           INTEGER NOT NULL DEFAULT 0,
    notes            TEXT
);
