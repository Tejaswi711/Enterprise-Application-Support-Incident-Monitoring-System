import random
from datetime import date, timedelta

from . import db

# Each job runs a real SQL query against the database.
# Two of them are deliberately broken so you can practise SQL troubleshooting.
JOBS = [
    {
        "job_name": "daily_claims_load",
        "description": "Counts newly received claims for the nightly load",
        "sql_text": "SELECT COUNT(*) AS received FROM claims WHERE status = 'RECEIVED'",
        "schedule": "Daily 01:00",
        "business_criticality": "High",
        "failure_rate": 0.08,
    },
    {
        "job_name": "member_eligibility_sync",
        "description": "Joins members to claims to refresh eligibility counts",
        "sql_text": (
            "SELECT m.member_id, m.plan_code, COUNT(c.claim_id) AS claim_count "
            "FROM members m LEFT JOIN claims c ON c.member_id = m.member_id "
            "WHERE m.status = 'ACTIVE' GROUP BY m.member_id, m.plan_code"
        ),
        "schedule": "Every 4 hours",
        "business_criticality": "High",
        "failure_rate": 0.10,
    },
    {
        "job_name": "billing_reconciliation",
        "description": "Compares billed and paid totals",
        "sql_text": "SELECT SUM(billed_amount) - SUM(paid_amount) AS variance FROM claims WHERE status = 'PAID'",
        "schedule": "Daily 03:00",
        "business_criticality": "Medium",
        "failure_rate": 0.06,
    },
    {
        # BROKEN ON PURPOSE: table does not exist (MISSING_OBJECT)
        "job_name": "pharmacy_rx_extract",
        "description": "Extracts pharmacy claims for the PBM vendor feed",
        "sql_text": "SELECT * FROM pharmacy_claims WHERE fill_date >= '2026-01-01'",
        "schedule": "Daily 02:00",
        "business_criticality": "Medium",
        "failure_rate": 0.0,
    },
    {
        # BROKEN ON PURPOSE: typo in SELECT (SQL_SYNTAX)
        "job_name": "weekly_provider_report",
        "description": "Claim volume per provider for the weekly report",
        "sql_text": "SELEC provider_id, COUNT(*) AS claim_count FROM claims GROUP BY provider_id",
        "schedule": "Weekly Mon 06:00",
        "business_criticality": "Low",
        "failure_rate": 0.0,
    },
    {
        "job_name": "claims_archive_check",
        "description": "Finds claims older than 2020 that are ready for archiving",
        "sql_text": "SELECT claim_id FROM claims WHERE service_date < '2020-01-01'",
        "schedule": "Daily 05:00",
        "business_criticality": "Low",
        "failure_rate": 0.04,
    },
]

KB_ARTICLES = [
    {
        "error_category": "DB_CONNECTION",
        "title": "Database connection failure",
        "symptoms": "Can't connect to MySQL server, connection refused, lost connection during query.",
        "troubleshooting_steps": (
            "1. Check the database service: systemctl status mysql\n"
            "2. Test connectivity from the app server: nc -zv <db-host> 3306\n"
            "3. Check max connections: SHOW VARIABLES LIKE 'max_connections'; SHOW STATUS LIKE 'Threads_connected';\n"
            "4. Review the MySQL error log: tail -n 100 /var/log/mysql/error.log\n"
            "5. Confirm credentials and host in the application config\n"
            "6. Re-run the failed job once the connection is restored"
        ),
        "resolution": "Database service restarted after connection pool exhaustion. Job re-run successfully.",
    },
    {
        "error_category": "SQL_SYNTAX",
        "title": "SQL syntax error in job query",
        "symptoms": "Error 1064 / 'syntax error' when the job runs.",
        "troubleshooting_steps": (
            "1. Copy the job SQL from the jobs table and run it manually in a SQL client\n"
            "2. Look at the position the error points to (near '...')\n"
            "3. Check for typos in keywords, missing commas, unbalanced quotes or brackets\n"
            "4. Check for recent changes to the job definition (updated_at)\n"
            "5. Fix the SQL, test it, then update the job definition"
        ),
        "resolution": "Corrected a typo in the job SQL and redeployed the job definition.",
    },
    {
        "error_category": "MISSING_OBJECT",
        "title": "Table or column not found",
        "symptoms": "Error 1146 table doesn't exist / 1054 unknown column / 'no such table'.",
        "troubleshooting_steps": (
            "1. Confirm the object exists: SHOW TABLES LIKE '<table>'; DESCRIBE <table>;\n"
            "2. Check you are connected to the right schema: SELECT DATABASE();\n"
            "3. Check whether a recent release renamed or dropped the object\n"
            "4. Check grants for the job's service account: SHOW GRANTS FOR CURRENT_USER;\n"
            "5. Point the job to the correct table or restore the missing object"
        ),
        "resolution": "Job referenced a table that was renamed in the last release. Query updated to the new table name.",
    },
    {
        "error_category": "TIMEOUT",
        "title": "Query timeout / lock wait timeout",
        "symptoms": "Error 1205 lock wait timeout exceeded, or query timed out.",
        "troubleshooting_steps": (
            "1. Find long running or blocking sessions: SHOW FULL PROCESSLIST;\n"
            "2. Check InnoDB lock waits: SELECT * FROM performance_schema.data_lock_waits;\n"
            "3. Run EXPLAIN on the job query and look for full table scans\n"
            "4. Check if another batch job runs in the same window\n"
            "5. Add an index or reschedule the job, then re-run"
        ),
        "resolution": "Blocking session from an overlapping batch job was cleared and the job was rescheduled.",
    },
    {
        "error_category": "DEADLOCK",
        "title": "Deadlock detected",
        "symptoms": "Error 1213 deadlock found when trying to get lock.",
        "troubleshooting_steps": (
            "1. Review the latest deadlock: SHOW ENGINE INNODB STATUS; (LATEST DETECTED DEADLOCK section)\n"
            "2. Identify the two transactions and the rows they locked\n"
            "3. Confirm the application retries the transaction\n"
            "4. Re-run the job; raise a problem ticket if it repeats"
        ),
        "resolution": "Transient deadlock with an overlapping update. Job re-run succeeded.",
    },
    {
        "error_category": "PERMISSION",
        "title": "Access denied",
        "symptoms": "Error 1045 access denied / 1142 command denied.",
        "troubleshooting_steps": (
            "1. Confirm which account the service uses\n"
            "2. SHOW GRANTS FOR '<user>'@'<host>';\n"
            "3. Check if the password was rotated recently\n"
            "4. Request access through the DBA team if grants are missing"
        ),
        "resolution": "Service account password had been rotated. Application secret updated.",
    },
    {
        "error_category": "HTTP_5XX",
        "title": "API returning HTTP 5xx",
        "symptoms": "Users or upstream systems receive 500/502/503 errors.",
        "troubleshooting_steps": (
            "1. grep the request_id in the application log to find the stack trace\n"
            "2. Check dependent services (database, auth) for errors at the same time\n"
            "3. Check CPU and memory on the app server: top, free -m, df -h\n"
            "4. Roll back the latest deployment if errors started after a release"
        ),
        "resolution": "Downstream database timeout caused 500 errors. Resolved after the DB issue was fixed.",
    },
    {
        "error_category": "OUT_OF_MEMORY",
        "title": "Out of memory",
        "symptoms": "OutOfMemoryError, heap space, process killed by OOM killer.",
        "troubleshooting_steps": (
            "1. Check memory: free -m and dmesg | grep -i oom\n"
            "2. Identify the process: ps aux --sort=-%mem | head\n"
            "3. Restart the service to restore availability\n"
            "4. Raise a problem ticket with heap settings and the request that triggered it"
        ),
        "resolution": "Service restarted. Heap size increased and a problem ticket raised for the memory leak.",
    },
    {
        "error_category": "APPLICATION_EXCEPTION",
        "title": "Unhandled application exception",
        "symptoms": "NullReference / NullPointer / unhandled exception in application code.",
        "troubleshooting_steps": (
            "1. Find the full stack trace in the application log\n"
            "2. Reproduce with the same input in a lower environment\n"
            "3. Check for bad or missing data in the records involved\n"
            "4. Apply a data fix or hand over to development with the details"
        ),
        "resolution": "Missing plan_code on a member record caused the exception. Data corrected and defect logged.",
    },
    {
        "error_category": "CONSTRAINT_VIOLATION",
        "title": "Constraint violation",
        "symptoms": "Duplicate entry / foreign key constraint fails.",
        "troubleshooting_steps": (
            "1. Find the duplicate or orphan rows with a GROUP BY ... HAVING COUNT(*) > 1 query\n"
            "2. Check whether the source file was loaded twice\n"
            "3. Remove or correct the bad rows and re-run"
        ),
        "resolution": "Source file had been loaded twice. Duplicates removed and load re-run.",
    },
    {
        "error_category": "UNKNOWN",
        "title": "Unclassified error",
        "symptoms": "Error message does not match a known pattern.",
        "troubleshooting_steps": (
            "1. Read the full error message and surrounding log lines\n"
            "2. Search past incidents for the same message\n"
            "3. Engage the owning team and document findings in work notes"
        ),
        "resolution": "Investigated with the owning team and resolved.",
    },
]

FIRST = ["Ava", "Liam", "Maya", "Noah", "Priya", "Ethan", "Sara", "Ravi", "Emma", "Omar"]
LAST = ["Patel", "Smith", "Garcia", "Reddy", "Johnson", "Nguyen", "Brown", "Khan"]


def _seed_business_tables():
    if db.fetch_one("SELECT COUNT(*) AS n FROM members")["n"]:
        return
    rng = random.Random(42)
    members = []
    for i in range(1, 41):
        members.append((
            1000 + i, rng.choice(FIRST), rng.choice(LAST),
            rng.choice(["HMO-GOLD", "PPO-SILVER", "EPO-BRONZE"]),
            rng.choices(["ACTIVE", "TERMED"], weights=[85, 15])[0],
            str(date(2023, 1, 1) + timedelta(days=rng.randint(0, 900))),
        ))
    db.execute_many("INSERT INTO members VALUES (%s, %s, %s, %s, %s, %s)", members)

    claims = []
    for i in range(1, 251):
        billed = round(rng.uniform(80, 4500), 2)
        claims.append((
            50000 + i, rng.choice(members)[0], rng.randint(700, 720),
            str(date(2019, 6, 1) + timedelta(days=rng.randint(0, 2700))),
            billed, round(billed * rng.uniform(0.4, 0.95), 2),
            rng.choice(["RECEIVED", "PAID", "PAID", "DENIED", "PENDED"]),
        ))
    db.execute_many("INSERT INTO claims VALUES (%s, %s, %s, %s, %s, %s, %s)", claims)


def seed_reference_data():
    _seed_business_tables()
    for job in JOBS:
        if not db.fetch_one("SELECT job_id FROM jobs WHERE job_name = %s", (job["job_name"],)):
            db.execute(
                "INSERT INTO jobs (job_name, description, sql_text, schedule, business_criticality, "
                "failure_rate, is_active, updated_at) VALUES (%s, %s, %s, %s, %s, %s, 1, %s)",
                (job["job_name"], job["description"], job["sql_text"], job["schedule"],
                 job["business_criticality"], job["failure_rate"], db.to_str(db.now())),
            )
    for kb in KB_ARTICLES:
        if not db.fetch_one("SELECT kb_id FROM kb_articles WHERE error_category = %s", (kb["error_category"],)):
            db.execute(
                "INSERT INTO kb_articles (error_category, title, symptoms, troubleshooting_steps, resolution) "
                "VALUES (%s, %s, %s, %s, %s)",
                (kb["error_category"], kb["title"], kb["symptoms"], kb["troubleshooting_steps"], kb["resolution"]),
            )
