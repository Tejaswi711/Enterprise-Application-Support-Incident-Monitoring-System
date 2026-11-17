
import hashlib
import random
import re
from collections import defaultdict
from datetime import timedelta

from . import config, db, incidents, rules

LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(?P<level>[A-Z]+)\s+\[(?P<component>[^\]]+)\]\s+(?P<message>.*)$"
)

INFO_LINES = [
    ("claims-api", "INFO", "POST /api/v1/claims 201 in {n} ms"),
    ("claims-api", "INFO", "GET /api/v1/claims/{n} 200 in 38 ms"),
    ("member-portal", "INFO", "User session started for member {n}"),
    ("billing-service", "INFO", "Invoice batch {n} generated"),
    ("auth-service", "INFO", "Token issued for client portal-web"),
    ("notification-service", "INFO", "Email queued for member {n}"),
    ("claims-api", "WARN", "Slow query detected: 2{n} ms on claims lookup"),
    ("auth-service", "WARN", "Login failed for member {n}: invalid credentials"),
]

ERROR_LINES = [
    ("billing-service", "ERROR", "Database connection failed: Can't connect to MySQL server on 'db-prod-01' (111)"),
    ("claims-api", "ERROR", "HTTP 500 Internal Server Error on POST /api/v1/claims request_id={n}"),
    ("claims-api", "ERROR", "Query timed out after 30000 ms: SELECT * FROM claims WHERE member_id = {n}"),
    ("member-portal", "ERROR", "NullReferenceException in EligibilityController.GetCoverage line {n}"),
    ("auth-service", "ERROR", "Access denied for user 'svc_auth'@'10.0.4.{n}' (using password: YES)"),
    ("notification-service", "ERROR", "SMTP relay service unavailable, message {n} requeued"),
    ("billing-service", "CRITICAL", "OutOfMemoryError: Java heap space in InvoiceGenerator"),
]


# ---------------------------------------------------------------- simulation
def simulate_app_logs(lines=60, start=None, minutes=60, error_rate=0.15, rng=None, path=None):
    """Append simulated log lines spread across `minutes` starting at `start`."""
    rng = rng or random
    path = path or config.APP_LOG_FILE
    start = db.to_dt(start) or (db.now() - timedelta(minutes=minutes))
    burst = rng.choice(ERROR_LINES[:-1])  # one error repeats in bursts so it crosses the threshold
    stamps = sorted(start + timedelta(seconds=rng.randint(0, minutes * 60)) for _ in range(lines))

    with open(path, "a") as fh:
        for ts in stamps:
            roll = rng.random()
            if roll < error_rate * 0.5:
                comp, level, msg = burst
            elif roll < error_rate:
                comp, level, msg = rng.choice(ERROR_LINES[:-1] if rng.random() > 0.08 else ERROR_LINES)
            else:
                comp, level, msg = rng.choice(INFO_LINES)
            fh.write(f"{db.to_str(ts)} {level} [{comp}] {msg.format(n=rng.randint(100, 999))}\n")
    return lines


# ---------------------------------------------------------------- analysis
def parse_line(line):
    m = LINE_RE.match(line.strip())
    return m.groupdict() if m else None


def signature_for(component, message):
    """Normalise numbers and quoted values so repeats of the same error group together."""
    normalised = re.sub(r"'[^']*'", "'?'", message)
    normalised = re.sub(r"\d+", "N", normalised)
    return hashlib.md5(f"{component}|{normalised}".encode()).hexdigest()[:16], normalised


def _read_offset(path):
    try:
        offset = int(config.ANALYZER_STATE_FILE.read_text().strip())
    except (FileNotFoundError, ValueError):
        return 0
    return 0 if offset > path.stat().st_size else offset  # file was rotated or truncated


def analyze_logs(path=None, from_start=False):
    path = path or config.APP_LOG_FILE
    if not path.exists():
        return {"lines_read": 0, "levels": {}, "groups": [], "incidents_created": 0, "incidents_updated": 0}

    offset = 0 if from_start else _read_offset(path)
    with open(path) as fh:
        fh.seek(offset)
        lines = fh.readlines()
        new_offset = fh.tell()

    levels = defaultdict(int)
    groups = {}
    processed_at = db.to_str(db.now())
    for line in lines:
        rec = parse_line(line)
        if not rec:
            levels["UNPARSED"] += 1
            continue
        levels[rec["level"]] += 1
        if rec["level"] not in ("ERROR", "CRITICAL"):
            continue
        sig, normalised = signature_for(rec["component"], rec["message"])
        category = rules.classify_error(rec["message"])
        event_id = db.execute(
            "INSERT INTO log_events (log_timestamp, level, component, message, signature, error_category, "
            "processed_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (rec["ts"], rec["level"], rec["component"], rec["message"], sig, category, processed_at),
        )
        g = groups.setdefault(sig, {"signature": sig, "component": rec["component"], "pattern": normalised,
                                    "category": category, "count": 0, "critical": False,
                                    "first_seen": rec["ts"], "last_seen": rec["ts"], "sample": rec["message"],
                                    "event_ids": []})
        g["count"] += 1
        g["critical"] = g["critical"] or rec["level"] == "CRITICAL"
        g["last_seen"] = rec["ts"]
        g["event_ids"].append(event_id)

    created = updated = 0
    for g in groups.values():
        if not (g["critical"] or g["count"] >= config.LOG_ERROR_THRESHOLD):
            continue
        criticality = config.COMPONENT_CRITICALITY.get(g["component"], "Medium")
        incident_id, is_new = incidents.raise_incident(
            title=f"[{g['component']}] {g['category']}: {g['pattern'][:120]}",
            description=(f"{g['count']} occurrence(s) between {g['first_seen']} and {g['last_seen']}.\n"
                         f"Sample: {g['sample']}"),
            source="LOG_MONITOR",
            source_ref=f"{g['component']}:{g['signature']}",
            error_category=g["category"],
            impact=rules.IMPACT_BY_CRITICALITY[criticality],
            urgency=1 if g["critical"] else rules.URGENCY_BY_CATEGORY.get(g["category"], 2),
            created_at=g["last_seen"],
        )
        created += is_new
        updated += not is_new
        for eid in g["event_ids"]:
            db.execute("UPDATE log_events SET incident_id = %s WHERE event_id = %s", (incident_id, eid))

    config.ANALYZER_STATE_FILE.write_text(str(new_offset))
    top = sorted(groups.values(), key=lambda x: -x["count"])
    return {
        "lines_read": len(lines),
        "levels": dict(levels),
        "groups": [{k: v for k, v in g.items() if k != "event_ids"} for g in top],
        "incidents_created": created,
        "incidents_updated": updated,
    }


def recent_log_errors(limit=200):
    return db.fetch_all(f"SELECT * FROM log_events ORDER BY log_timestamp DESC LIMIT {int(limit)}")
