
import logging
import random
import time
from datetime import timedelta

from . import config, db, incidents, rules

logger = logging.getLogger("job-scheduler")
if not logger.handlers:
    handler = logging.FileHandler(config.JOB_LOG_FILE)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [job-scheduler] %(message)s",
                                           datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class SimulatedDatabaseError(Exception):
    """Raised to imitate infrastructure problems a real MySQL server would return."""


INJECTED_FAILURES = [
    ("(2003, \"Can't connect to MySQL server on 'db-prod-01' ([Errno 111] Connection refused)\")", 5),
    ("(2013, 'Lost connection to MySQL server during query')", 2),
    ("(1205, 'Lock wait timeout exceeded; try restarting transaction')", 3),
    ("(1213, 'Deadlock found when trying to get lock; try restarting transaction')", 2),
]


def get_jobs(active_only=True):
    sql = "SELECT * FROM jobs" + (" WHERE is_active = 1" if active_only else "") + " ORDER BY job_id"
    return db.fetch_all(sql)


def update_job_sql(job_id, sql_text):
    """Used when resolving an incident by fixing the job's query."""
    db.execute("UPDATE jobs SET sql_text = %s, updated_at = %s WHERE job_id = %s",
               (sql_text, db.to_str(db.now()), job_id))


def run_job(job, run_time=None, rng=None):
    rng = rng or random
    started = db.to_dt(run_time) or db.now()
    t0 = time.perf_counter()
    status, rows, category, error = "SUCCESS", None, None, None

    try:
        if rng.random() < float(job["failure_rate"]):
            messages, weights = zip(*INJECTED_FAILURES)
            raise SimulatedDatabaseError(rng.choices(messages, weights=weights)[0])
        conn = db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(job["sql_text"])
            rows = len(cur.fetchall())
        finally:
            conn.close()
    except Exception as exc:  # any DB error is a job failure we want to capture
        status, error = "FAILED", str(exc)
        category = rules.classify_error(error)

    # real elapsed time plus a simulated batch duration so the numbers look realistic
    duration_ms = int((time.perf_counter() - t0) * 1000) + rng.randint(800, 45000)
    ended = started + timedelta(milliseconds=duration_ms)

    run_id = db.execute(
        "INSERT INTO job_runs (job_id, status, started_at, ended_at, duration_ms, rows_returned, "
        "error_category, error_message) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (job["job_id"], status, db.to_str(started), db.to_str(ended), duration_ms, rows, category, error),
    )

    incident_id = None
    if status == "FAILED":
        logger.error("Job %s FAILED (%s): %s", job["job_name"], category, error)
        incident_id, _ = incidents.raise_incident(
            title=f"[{job['job_name']}] job failed: {category}",
            description=f"Job {job['job_name']} failed at {db.to_str(started)}.\nSQL: {job['sql_text']}\nError: {error}",
            source="JOB_MONITOR",
            source_ref=job["job_name"],
            error_category=category,
            impact=rules.IMPACT_BY_CRITICALITY[job["business_criticality"]],
            urgency=rules.URGENCY_BY_CATEGORY.get(category, 2),
            created_at=ended,
            assigned_group="Database Support" if category in ("DB_CONNECTION", "DEADLOCK", "TIMEOUT")
            else "Application Support",
        )
        db.execute("UPDATE job_runs SET incident_id = %s WHERE run_id = %s", (incident_id, run_id))
    else:
        logger.info("Job %s SUCCESS, %s rows in %s ms", job["job_name"], rows, duration_ms)

    return {"run_id": run_id, "job_name": job["job_name"], "status": status,
            "error_category": category, "error": error, "incident_id": incident_id}


def run_all_jobs(run_time=None, rng=None):
    return [run_job(job, run_time, rng) for job in get_jobs()]


def recent_runs(limit=200, status=None):
    sql = ("SELECT r.*, j.job_name, j.business_criticality FROM job_runs r "
           "JOIN jobs j ON j.job_id = r.job_id")
    params = ()
    if status:
        sql += " WHERE r.status = %s"
        params = (status,)
    return db.fetch_all(sql + f" ORDER BY r.started_at DESC LIMIT {int(limit)}", params)
