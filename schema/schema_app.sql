-- TenderBD app tables — PostgreSQL (Supabase free tier).
-- Companion to tenderbd_scraper/schema.sql (tenders + fetch_runs).
-- Timestamps are TIMESTAMPTZ; the API serializes ISO strings.
-- No foreign keys (mirrors the prototype); indexes on user_id columns.

CREATE TABLE IF NOT EXISTS users (
    id                  SERIAL PRIMARY KEY,
    email               TEXT NOT NULL UNIQUE,
    password_hash       TEXT NOT NULL,
    name                TEXT NOT NULL,
    session_token       TEXT,
    session_expires_at  TIMESTAMPTZ,
    reset_token         TEXT,
    reset_expires_at    TIMESTAMPTZ,
    is_admin            BOOLEAN NOT NULL DEFAULT false,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_users_email          ON users (email);
CREATE INDEX IF NOT EXISTS idx_users_session_token  ON users (session_token);

CREATE TABLE IF NOT EXISTS sign_in_attempts (
    email               TEXT PRIMARY KEY,
    fail_count          INTEGER NOT NULL DEFAULT 0,
    window_started_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    locked_until        TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS subscriptions (
    user_id         INTEGER PRIMARY KEY,
    plan            TEXT NOT NULL DEFAULT 'Free',
    payment_method  TEXT,
    status          TEXT NOT NULL DEFAULT 'Active',
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS companies (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER NOT NULL UNIQUE,
    company_name        TEXT NOT NULL,
    trade_license_no    TEXT,
    tin_no              TEXT,
    incorporation_year  INTEGER,
    annual_turnover_bdt BIGINT,
    liquid_assets_bdt   BIGINT,
    categories          TEXT,
    districts           TEXT,
    similar_works       JSONB,
    key_personnel       TEXT,
    equipment           TEXT,
    about               TEXT,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_companies_user_id ON companies (user_id);

CREATE TABLE IF NOT EXISTS documents (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    doc_type    TEXT NOT NULL,
    file_name   TEXT NOT NULL,
    mime_type   TEXT,
    size_bytes  INTEGER NOT NULL,
    data        BYTEA NOT NULL,
    status      TEXT NOT NULL DEFAULT 'Declared',
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents (user_id);

CREATE TABLE IF NOT EXISTS favourites (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    tender_id   BIGINT NOT NULL,
    stage       TEXT NOT NULL DEFAULT 'Shortlisted',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, tender_id)
);

CREATE INDEX IF NOT EXISTS idx_favourites_user_id   ON favourites (user_id);
CREATE INDEX IF NOT EXISTS idx_favourites_tender_id ON favourites (tender_id);

CREATE TABLE IF NOT EXISTS alert_prefs (
    user_id         INTEGER PRIMARY KEY,
    keywords        TEXT,
    categories      TEXT,
    districts       TEXT,
    organisations   TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS jv_posts (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL,
    tender_id       BIGINT,
    tender_title    TEXT,
    title           TEXT NOT NULL,
    need_description TEXT NOT NULL,
    looking_for     TEXT,
    share_offered   TEXT,
    status          TEXT NOT NULL DEFAULT 'Open',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_jv_posts_user_id   ON jv_posts (user_id);
CREATE INDEX IF NOT EXISTS idx_jv_posts_tender_id ON jv_posts (tender_id);

CREATE TABLE IF NOT EXISTS jv_interests (
    id          SERIAL PRIMARY KEY,
    post_id     INTEGER NOT NULL,
    user_id     INTEGER NOT NULL,
    message     TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_jv_interests_post_id ON jv_interests (post_id);
CREATE INDEX IF NOT EXISTS idx_jv_interests_user_id ON jv_interests (user_id);

CREATE TABLE IF NOT EXISTS jv_rooms (
    id          SERIAL PRIMARY KEY,
    post_id     INTEGER NOT NULL UNIQUE,
    title       TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_jv_rooms_post_id ON jv_rooms (post_id);

CREATE TABLE IF NOT EXISTS jv_messages (
    id          SERIAL PRIMARY KEY,
    room_id     INTEGER NOT NULL,
    user_id     INTEGER NOT NULL,
    sender_name TEXT NOT NULL,
    body        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_jv_messages_room_id ON jv_messages (room_id);

CREATE TABLE IF NOT EXISTS payment_submissions (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL,
    plan            TEXT NOT NULL,
    method          TEXT NOT NULL,
    transaction_id  TEXT NOT NULL,
    sender_number   TEXT,
    amount_bdt      INTEGER NOT NULL,
    status          TEXT NOT NULL DEFAULT 'Pending',
    submitted_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at     TIMESTAMPTZ,
    review_note     TEXT
);

CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payment_submissions (user_id);
CREATE INDEX IF NOT EXISTS idx_payments_status  ON payment_submissions (status);

CREATE TABLE IF NOT EXISTS consulting_requests (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    tender_id   BIGINT,
    tender_title TEXT,
    topic       TEXT NOT NULL,
    message     TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'Open',
    reply       TEXT,
    replied_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_consulting_user_id ON consulting_requests (user_id);
