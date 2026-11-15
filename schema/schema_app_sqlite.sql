-- TenderBD app tables — SQLite fallback for local development and tests.
-- Same tables as schema_app.sql; datetimes stored as ISO-8601 text,
-- JSON stored as text, file bytes as BLOB. The AppStore class
-- translates placeholders and coerces values automatically.

CREATE TABLE IF NOT EXISTS users (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    email               TEXT NOT NULL UNIQUE,
    password_hash       TEXT NOT NULL,
    name                TEXT NOT NULL,
    session_token       TEXT,
    session_expires_at  TEXT,
    reset_token         TEXT,
    reset_expires_at    TEXT,
    is_admin            INTEGER NOT NULL DEFAULT 0,
    created_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_email          ON users (email);
CREATE INDEX IF NOT EXISTS idx_users_session_token  ON users (session_token);

CREATE TABLE IF NOT EXISTS sign_in_attempts (
    email               TEXT PRIMARY KEY,
    fail_count          INTEGER NOT NULL DEFAULT 0,
    window_started_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    locked_until        TEXT
);

CREATE TABLE IF NOT EXISTS subscriptions (
    user_id         INTEGER PRIMARY KEY,
    plan            TEXT NOT NULL DEFAULT 'Free',
    payment_method  TEXT,
    status          TEXT NOT NULL DEFAULT 'Active',
    updated_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS companies (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL UNIQUE,
    company_name        TEXT NOT NULL,
    trade_license_no    TEXT,
    tin_no              TEXT,
    incorporation_year  INTEGER,
    annual_turnover_bdt INTEGER,
    liquid_assets_bdt   INTEGER,
    categories          TEXT,
    districts           TEXT,
    similar_works       TEXT,
    key_personnel       TEXT,
    equipment           TEXT,
    about               TEXT,
    updated_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_companies_user_id ON companies (user_id);

CREATE TABLE IF NOT EXISTS documents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    doc_type    TEXT NOT NULL,
    file_name   TEXT NOT NULL,
    mime_type   TEXT,
    size_bytes  INTEGER NOT NULL,
    data        BLOB NOT NULL,
    status      TEXT NOT NULL DEFAULT 'Declared',
    uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents (user_id);

CREATE TABLE IF NOT EXISTS favourites (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    tender_id   INTEGER NOT NULL,
    stage       TEXT NOT NULL DEFAULT 'Shortlisted',
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
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
    updated_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS jv_posts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    tender_id       INTEGER,
    tender_title    TEXT,
    title           TEXT NOT NULL,
    need_description TEXT NOT NULL,
    looking_for     TEXT,
    share_offered   TEXT,
    status          TEXT NOT NULL DEFAULT 'Open',
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_jv_posts_user_id   ON jv_posts (user_id);
CREATE INDEX IF NOT EXISTS idx_jv_posts_tender_id ON jv_posts (tender_id);

CREATE TABLE IF NOT EXISTS jv_interests (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id     INTEGER NOT NULL,
    user_id     INTEGER NOT NULL,
    message     TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_jv_interests_post_id ON jv_interests (post_id);
CREATE INDEX IF NOT EXISTS idx_jv_interests_user_id ON jv_interests (user_id);

CREATE TABLE IF NOT EXISTS jv_rooms (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id     INTEGER NOT NULL UNIQUE,
    title       TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_jv_rooms_post_id ON jv_rooms (post_id);

CREATE TABLE IF NOT EXISTS jv_messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id     INTEGER NOT NULL,
    user_id     INTEGER NOT NULL,
    sender_name TEXT NOT NULL,
    body        TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_jv_messages_room_id ON jv_messages (room_id);

CREATE TABLE IF NOT EXISTS payment_submissions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    plan            TEXT NOT NULL,
    method          TEXT NOT NULL,
    transaction_id  TEXT NOT NULL,
    sender_number   TEXT,
    amount_bdt      INTEGER NOT NULL,
    status          TEXT NOT NULL DEFAULT 'Pending',
    submitted_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_at     TEXT,
    review_note     TEXT
);

CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payment_submissions (user_id);
CREATE INDEX IF NOT EXISTS idx_payments_status  ON payment_submissions (status);

CREATE TABLE IF NOT EXISTS consulting_requests (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    tender_id   INTEGER,
    tender_title TEXT,
    topic       TEXT NOT NULL,
    message     TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'Open',
    reply       TEXT,
    replied_at  TEXT,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_consulting_user_id ON consulting_requests (user_id);
