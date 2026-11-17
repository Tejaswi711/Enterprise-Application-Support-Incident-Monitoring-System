from . import db, incidents, job_monitor, log_monitor


def run_cycle(simulate_logs=True, run_time=None, rng=None):
    now = db.to_dt(run_time) or db.now()
    job_results = job_monitor.run_all_jobs(run_time=now, rng=rng)
    if simulate_logs:
        log_monitor.simulate_app_logs(lines=60, minutes=30, rng=rng)
    log_result = log_monitor.analyze_logs()
    sla_changed = incidents.update_sla_flags(now)
    escalated = incidents.run_escalations(now)
    return {
        "ran_at": db.to_str(now),
        "jobs_run": len(job_results),
        "jobs_failed": sum(1 for r in job_results if r["status"] == "FAILED"),
        "failed_jobs": [r for r in job_results if r["status"] == "FAILED"],
        "log_lines_read": log_result["lines_read"],
        "log_levels": log_result["levels"],
        "log_incidents_created": log_result["incidents_created"],
        "sla_flags_updated": sla_changed,
        "escalations": escalated,
    }
