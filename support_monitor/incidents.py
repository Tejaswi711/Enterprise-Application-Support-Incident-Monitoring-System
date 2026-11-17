from datetime import timedelta

from . import config, db, rules

OPEN_SQL = "status IN (%s, %s, %s)"


# ---------------------------------------------------------------- notes / KB
def add_note(incident_id, note_type, text, author="system", at=None):
    db.execute(
        "INSERT INTO incident_notes (incident_id, note_type, note_text, author, created_at) "
        "VALUES (%s, %s, %s, %s, %s)",
        (incident_id, note_type, text, author, db.to_str(at or db.now())),
    )


def get_kb_article(error_category):
    return db.fetch_one("SELECT * FROM kb_articles WHERE error_category = %s", (error_category,))


# ---------------------------------------------------------------- create
def raise_incident(title, description, source, source_ref, error_category,
                   impact, urgency, created_at=None, assigned_group="Application Support"):
    """Create an incident, or add a recurrence to the open one for the same problem.

    Returns (incident_id, created_new).
    """
    created_at = db.to_dt(created_at) or db.now()
    existing = db.fetch_one(
        f"SELECT * FROM incidents WHERE source_ref = %s AND error_category = %s AND {OPEN_SQL}",
        (source_ref, error_category, *config.OPEN_STATUSES),
    )
    if existing:
        db.execute(
            "UPDATE incidents SET occurrence_count = occurrence_count + 1, last_occurrence_at = %s "
            "WHERE incident_id = %s",
            (db.to_str(created_at), existing["incident_id"]),
        )
        add_note(existing["incident_id"], "SYSTEM",
                 f"Recurrence #{existing['occurrence_count'] + 1} detected: {description[:300]}", at=created_at)
        return existing["incident_id"], False

    priority = rules.calculate_priority(impact, urgency)
    response_due, resolution_due = rules.calculate_deadlines(priority, created_at)
    incident_id = db.execute(
        "INSERT INTO incidents (title, description, source, source_ref, error_category, impact, urgency, "
        "priority, severity, status, assigned_group, created_at, last_occurrence_at, response_due, resolution_due) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'New', %s, %s, %s, %s, %s)",
        (title[:255], description, source, source_ref, error_category, impact, urgency,
         priority, rules.severity_for(priority), assigned_group,
         db.to_str(created_at), db.to_str(created_at), db.to_str(response_due), db.to_str(resolution_due)),
    )
    db.execute("UPDATE incidents SET incident_number = %s WHERE incident_id = %s",
               (f"INC{100000 + incident_id}", incident_id))

    add_note(incident_id, "SYSTEM",
             f"Auto created by {source}. Priority {priority} (impact {impact} x urgency {urgency}). "
             f"Respond by {db.to_str(response_due)}, resolve by {db.to_str(resolution_due)}.",
             at=created_at)
    kb = get_kb_article(error_category)
    if kb:
        add_note(incident_id, "TROUBLESHOOTING",
                 f"Suggested steps from KB '{kb['title']}':\n{kb['troubleshooting_steps']}", at=created_at)
    return incident_id, True


# ---------------------------------------------------------------- lifecycle
def acknowledge(incident_id, user, at=None):
    at = db.to_dt(at) or db.now()
    inc = get_incident(incident_id)
    if not inc or inc["acknowledged_at"]:
        return inc
    breached = rules.response_breached({**inc, "acknowledged_at": at}, at)
    db.execute(
        "UPDATE incidents SET status = 'In Progress', acknowledged_at = %s, assigned_to = %s, "
        "response_breached = %s WHERE incident_id = %s",
        (db.to_str(at), user, int(breached), incident_id),
    )
    add_note(incident_id, "WORK_NOTE", f"Acknowledged and assigned to {user}.", author=user, at=at)
    return get_incident(incident_id)


def resolve(incident_id, root_cause, resolution_notes, user, at=None):
    at = db.to_dt(at) or db.now()
    inc = get_incident(incident_id)
    if not inc or not rules.is_open(inc):
        return inc
    if not inc["acknowledged_at"]:
        acknowledge(incident_id, user, at)
        inc = get_incident(incident_id)
    breached = rules.resolution_breached({**inc, "resolved_at": at}, at)
    db.execute(
        "UPDATE incidents SET status = 'Resolved', resolved_at = %s, root_cause = %s, "
        "resolution_notes = %s, resolution_breached = %s WHERE incident_id = %s",
        (db.to_str(at), root_cause, resolution_notes, int(breached), incident_id),
    )
    add_note(incident_id, "RESOLUTION", f"Root cause: {root_cause}\nResolution: {resolution_notes}",
             author=user, at=at)
    return get_incident(incident_id)


# ---------------------------------------------------------------- SLA + escalation sweeps
def update_sla_flags(now=None):
    """Mark open incidents whose response or resolution deadline has passed."""
    now = db.to_dt(now) or db.now()
    changed = 0
    for inc in list_incidents(open_only=True):
        resp, reso = int(rules.response_breached(inc, now)), int(rules.resolution_breached(inc, now))
        if resp != inc["response_breached"] or reso != inc["resolution_breached"]:
            db.execute("UPDATE incidents SET response_breached = %s, resolution_breached = %s WHERE incident_id = %s",
                       (resp, reso, inc["incident_id"]))
            changed += 1
    return changed


def run_escalations(now=None):
    """Escalate open incidents that meet an escalation rule. Returns the escalated incidents."""
    now = db.to_dt(now) or db.now()
    escalated = []
    for inc in list_incidents(open_only=True):
        level, reason = rules.decide_escalation(inc, now)
        if level > inc["escalation_level"]:
            db.execute("UPDATE incidents SET escalation_level = %s, escalated_at = %s WHERE incident_id = %s",
                       (level, db.to_str(now), inc["incident_id"]))
            add_note(inc["incident_id"], "ESCALATION",
                     f"Escalated to level {level} ({config.ESCALATION_TARGETS[level]}). Reason: {reason}.", at=now)
            escalated.append({"incident_number": inc["incident_number"], "level": level, "reason": reason})
    return escalated


# ---------------------------------------------------------------- queries
def get_incident(incident_id, with_notes=False):
    inc = db.fetch_one("SELECT * FROM incidents WHERE incident_id = %s", (incident_id,))
    if inc and with_notes:
        inc["notes"] = db.fetch_all(
            "SELECT * FROM incident_notes WHERE incident_id = %s ORDER BY note_id", (incident_id,))
    return inc


def find_by_number(number):
    return db.fetch_one("SELECT * FROM incidents WHERE incident_number = %s", (number,))


def list_incidents(status=None, priority=None, open_only=False):
    sql, params = "SELECT * FROM incidents WHERE 1 = 1", []
    if open_only:
        sql += f" AND {OPEN_SQL}"
        params += list(config.OPEN_STATUSES)
    if status:
        sql += " AND status = %s"
        params.append(status)
    if priority:
        sql += " AND priority = %s"
        params.append(priority)
    return db.fetch_all(sql + " ORDER BY priority, created_at DESC", tuple(params))


def sla_breaches():
    return db.fetch_all(
        "SELECT * FROM incidents WHERE response_breached = 1 OR resolution_breached = 1 ORDER BY created_at DESC")


def escalated_incidents():
    return db.fetch_all(
        f"SELECT * FROM incidents WHERE escalation_level > 0 AND {OPEN_SQL} "
        "ORDER BY escalation_level DESC, priority", config.OPEN_STATUSES)


def summary(now=None):
    """Headline numbers for the dashboard and the /api/summary endpoint."""
    now = db.to_dt(now) or db.now()
    incidents = db.fetch_all("SELECT * FROM incidents")
    open_inc = [i for i in incidents if rules.is_open(i)]
    resolved = [i for i in incidents if not rules.is_open(i)]
    since = db.to_str(now - timedelta(hours=24))
    runs_24h = db.fetch_all("SELECT status FROM job_runs WHERE started_at >= %s", (since,))
    failed_24h = sum(1 for r in runs_24h if r["status"] == "FAILED")

    mttr = [(db.to_dt(i["resolved_at"]) - db.to_dt(i["created_at"])).total_seconds() / 60 for i in resolved]
    met = [i for i in resolved if not i["resolution_breached"]]
    return {
        "open_incidents": len(open_inc),
        "resolved_incidents": len(resolved),
        "p1_open": sum(1 for i in open_inc if i["priority"] == "P1"),
        "sla_breaches": sum(1 for i in incidents if i["response_breached"] or i["resolution_breached"]),
        "escalated_open": sum(1 for i in open_inc if i["escalation_level"] > 0),
        "job_runs_24h": len(runs_24h),
        "failed_jobs_24h": failed_24h,
        "job_success_rate_24h": round(100 * (1 - failed_24h / len(runs_24h)), 1) if runs_24h else None,
        "mttr_minutes": round(sum(mttr) / len(mttr), 1) if mttr else None,
        "sla_compliance_pct": round(100 * len(met) / len(resolved), 1) if resolved else None,
    }
