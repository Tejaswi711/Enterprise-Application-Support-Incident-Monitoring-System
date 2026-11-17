
import random
from datetime import timedelta

from . import config, db, incidents, job_monitor, log_monitor

ANALYSTS = ["Prashanthi E.", "J. Carter", "A. Rao", "M. Lopez"]


def _work_the_queue(slot_time, rng):
    for inc in incidents.list_incidents(open_only=True):
        created = db.to_dt(inc["created_at"])
        if not inc["acknowledged_at"] and rng.random() < 0.85:
            ack_at = created + timedelta(minutes=rng.choice([5, 10, 12, 20, 35, 60, 240]))
            if ack_at <= slot_time:
                incidents.acknowledge(inc["incident_id"], rng.choice(ANALYSTS), ack_at)
        inc = incidents.get_incident(inc["incident_id"])
        if inc["acknowledged_at"] and rng.random() < 0.55:
            resolved_at = db.to_dt(inc["acknowledged_at"]) + timedelta(minutes=rng.randint(20, 900))
            if resolved_at <= slot_time:
                kb = incidents.get_kb_article(inc["error_category"]) or {}
                incidents.add_note(inc["incident_id"], "TROUBLESHOOTING",
                                   "Followed KB steps, confirmed root cause in logs and database.",
                                   author=inc["assigned_to"], at=resolved_at - timedelta(minutes=5))
                incidents.resolve(inc["incident_id"],
                                  root_cause=kb.get("title", "See work notes"),
                                  resolution_notes=kb.get("resolution", "Resolved"),
                                  user=inc["assigned_to"], at=resolved_at)


def seed_demo(days=7, seed=7):
    rng = random.Random(seed)
    db.init_db(reset=True)
    for f in (config.APP_LOG_FILE, config.JOB_LOG_FILE):
        f.write_text("")
    config.ANALYZER_STATE_FILE.write_text("0")

    now = db.now()
    slot = now - timedelta(days=days)
    while slot < now:
        job_monitor.run_all_jobs(run_time=slot, rng=rng)
        log_monitor.simulate_app_logs(lines=40, start=slot, minutes=230, rng=rng)
        log_monitor.analyze_logs()
        if slot < now - timedelta(hours=20):  # leave the last day open so there is live work
            _work_the_queue(slot, rng)
        incidents.update_sla_flags(slot)
        incidents.run_escalations(slot)
        slot += timedelta(hours=4)

    incidents.update_sla_flags(now)
    incidents.run_escalations(now)
    return incidents.summary(now)
if __name__ == "__main__":
    summary = seed_demo()
    print("\n===== SUPPORT MONITOR DEMO =====")
    print(summary)