-- MySQL 8 version of the schema.
-- Create the database and user first (run as root):
--   CREATE DATABASE app_support;
--   CREATE USER 'support_user'@'localhost' IDENTIFIED BY 'support_pass';
--   GRANT ALL PRIVILEGES ON app_support.* TO 'support_user'@'localhost';

CREATE TABLE IF NOT EXISTS members (
    member_id       INT PRIMARY KEY,
    first_name      VARCHAR(50) NOT NULL,
    last_name       VARCHAR(50) NOT NULL,
    plan_code       VARCHAR(20) NOT NULL,
    status          VARCHAR(20) NOT NULL,
    effective_date  DATE NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS claims (
    claim_id        INT PRIMARY KEY,
    member_id       INT NOT NULL,
    provider_id     INT NOT NULL,
    service_date    DATE NOT NULL,
    billed_amount   DECIMAL(10,2) NOT NULL,
    paid_amount     DECIMAL(10,2) NOT NULL,
    status          VARCHAR(20) NOT NULL,
    FOREIGN KEY (member_id) REFERENCES members(member_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS jobs (
    job_id               INT AUTO_INCREMENT PRIMARY KEY,
    job_name             VARCHAR(100) NOT NULL UNIQUE,
    description          VARCHAR(255),
    sql_text             TEXT NOT NULL,
    schedule             VARCHAR(50),
    business_criticality VARCHAR(10) NOT NULL DEFAULT 'Medium',
    failure_rate         DECIMAL(4,2) NOT NULL DEFAULT 0,
    is_active            TINYINT NOT NULL DEFAULT 1,
    updated_at           DATETIME
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS incidents (
    incident_id         INT AUTO_INCREMENT PRIMARY KEY,
    incident_number     VARCHAR(20) UNIQUE,
    title               VARCHAR(255) NOT NULL,
    description         TEXT,
    source              VARCHAR(20) NOT NULL,
    source_ref          VARCHAR(255) NOT NULL,
    error_category      VARCHAR(40) NOT NULL,
    impact              TINYINT NOT NULL,
    urgency             TINYINT NOT NULL,
    priority            CHAR(2) NOT NULL,
    severity            VARCHAR(10) NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'New',
    assigned_group      VARCHAR(100),
    assigned_to         VARCHAR(100),
    created_at          DATETIME NOT NULL,
    last_occurrence_at  DATETIME,
    acknowledged_at     DATETIME,
    resolved_at         DATETIME,
    response_due        DATETIME NOT NULL,
    resolution_due      DATETIME NOT NULL,
    response_breached   TINYINT NOT NULL DEFAULT 0,
    resolution_breached TINYINT NOT NULL DEFAULT 0,
    escalation_level    TINYINT NOT NULL DEFAULT 0,
    escalated_at        DATETIME,
    occurrence_count    INT NOT NULL DEFAULT 1,
    root_cause          TEXT,
    resolution_notes    TEXT,
    INDEX idx_incidents_status (status),
    INDEX idx_incidents_source_ref (source_ref)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS job_runs (
    run_id          INT AUTO_INCREMENT PRIMARY KEY,
    job_id          INT NOT NULL,
    status          VARCHAR(10) NOT NULL,
    started_at      DATETIME NOT NULL,
    ended_at        DATETIME,
    duration_ms     INT,
    rows_returned   INT,
    error_category  VARCHAR(40),
    error_message   TEXT,
    incident_id     INT,
    INDEX idx_job_runs_started (started_at),
    FOREIGN KEY (job_id) REFERENCES jobs(job_id),
    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS incident_notes (
    note_id      INT AUTO_INCREMENT PRIMARY KEY,
    incident_id  INT NOT NULL,
    note_type    VARCHAR(20) NOT NULL,
    note_text    TEXT NOT NULL,
    author       VARCHAR(100) NOT NULL,
    created_at   DATETIME NOT NULL,
    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS kb_articles (
    kb_id                 INT AUTO_INCREMENT PRIMARY KEY,
    error_category        VARCHAR(40) NOT NULL UNIQUE,
    title                 VARCHAR(255) NOT NULL,
    symptoms              TEXT,
    troubleshooting_steps TEXT NOT NULL,
    resolution            TEXT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS log_events (
    event_id        INT AUTO_INCREMENT PRIMARY KEY,
    log_timestamp   DATETIME NOT NULL,
    level           VARCHAR(10) NOT NULL,
    component       VARCHAR(50) NOT NULL,
    message         TEXT NOT NULL,
    signature       VARCHAR(64) NOT NULL,
    error_category  VARCHAR(40),
    incident_id     INT,
    processed_at    DATETIME NOT NULL,
    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id)
) ENGINE=InnoDB;
