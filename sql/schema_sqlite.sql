-- SQLite version of the schema (default, zero setup).
-- Keep columns identical to schema_mysql.sql.

CREATE TABLE IF NOT EXISTS members (
    member_id       INTEGER PRIMARY KEY,
    first_name      TEXT NOT NULL,
    last_name       TEXT NOT NULL,
    plan_code       TEXT NOT NULL,
    status          TEXT NOT NULL,
    effective_date  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claims (
    claim_id        INTEGER PRIMARY KEY,
    member_id       INTEGER NOT NULL REFERENCES members(member_id),
    provider_id     INTEGER NOT NULL,
    service_date    TEXT NOT NULL,
    billed_amount   REAL NOT NULL,
    paid_amount     REAL NOT NULL,
    status          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    job_id               INTEGER PRIMARY KEY AUTOINCREMENT,
    job_name             TEXT NOT NULL UNIQUE,
    description          TEXT,
    sql_text             TEXT NOT NULL,
    schedule             TEXT,
    business_criticality TEXT NOT NULL DEFAULT 'Medium',
    failure_rate         REAL NOT NULL DEFAULT 0,
    is_active            INTEGER NOT NULL DEFAULT 1,
    updated_at           TEXT
);

CREATE TABLE IF NOT EXISTS incidents (
    incident_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_number     TEXT UNIQUE,
    title               TEXT NOT NULL,
    description         TEXT,
    source              TEXT NOT NULL,
    source_ref          TEXT NOT NULL,
    error_category      TEXT NOT NULL,
    impact              INTEGER NOT NULL,
    urgency             INTEGER NOT NULL,
    priority            TEXT NOT NULL,
    severity            TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'New',
    assigned_group      TEXT,
    assigned_to         TEXT,
    created_at          TEXT NOT NULL,
    last_occurrence_at  TEXT,
    acknowledged_at     TEXT,
    resolved_at         TEXT,
    response_due        TEXT NOT NULL,
    resolution_due      TEXT NOT NULL,
    response_breached   INTEGER NOT NULL DEFAULT 0,
    resolution_breached INTEGER NOT NULL DEFAULT 0,
    escalation_level    INTEGER NOT NULL DEFAULT 0,
    escalated_at        TEXT,
    occurrence_count    INTEGER NOT NULL DEFAULT 1,
    root_cause          TEXT,
    resolution_notes    TEXT
);

CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
CREATE INDEX IF NOT EXISTS idx_incidents_source_ref ON incidents(source_ref);

CREATE TABLE IF NOT EXISTS job_runs (
    run_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          INTEGER NOT NULL REFERENCES jobs(job_id),
    status          TEXT NOT NULL,
    started_at      TEXT NOT NULL,
    ended_at        TEXT,
    duration_ms     INTEGER,
    rows_returned   INTEGER,
    error_category  TEXT,
    error_message   TEXT,
    incident_id     INTEGER REFERENCES incidents(incident_id)
);

CREATE INDEX IF NOT EXISTS idx_job_runs_started ON job_runs(started_at);

CREATE TABLE IF NOT EXISTS incident_notes (
    note_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id  INTEGER NOT NULL REFERENCES incidents(incident_id),
    note_type    TEXT NOT NULL,
    note_text    TEXT NOT NULL,
    author       TEXT NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS kb_articles (
    kb_id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    error_category        TEXT NOT NULL UNIQUE,
    title                 TEXT NOT NULL,
    symptoms              TEXT,
    troubleshooting_steps TEXT NOT NULL,
    resolution            TEXT
);

CREATE TABLE IF NOT EXISTS log_events (
    event_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    log_timestamp   TEXT NOT NULL,
    level           TEXT NOT NULL,
    component       TEXT NOT NULL,
    message         TEXT NOT NULL,
    signature       TEXT NOT NULL,
    error_category  TEXT,
    incident_id     INTEGER REFERENCES incidents(incident_id),
    processed_at    TEXT NOT NULL
);
