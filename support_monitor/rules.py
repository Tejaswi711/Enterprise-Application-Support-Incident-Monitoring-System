
import re
from datetime import timedelta

from . import config
from .db import to_dt

# ---------------------------------------------------------------- error classification
# Order matters: the first matching category wins.
ERROR_PATTERNS = [
    ("DB_CONNECTION", [r"can't connect", r"connection refused", r"lost connection", r"server has gone away",
                       r"unable to open database", r"connection reset", r"\(2003", r"\(2006", r"\(2013"]),
    ("PERMISSION", [r"access denied", r"permission denied", r"command denied", r"\(1045", r"\(1142"]),
    ("DEADLOCK", [r"deadlock", r"\(1213"]),
    ("TIMEOUT", [r"timed? ?out", r"\(1205"]),
    ("SQL_SYNTAX", [r"syntax error", r"error in your sql syntax", r"\(1064"]),
    ("MISSING_OBJECT", [r"no such table", r"no such column", r"doesn't exist", r"unknown column",
                        r"\(1146", r"\(1054"]),
    ("CONSTRAINT_VIOLATION", [r"unique constraint", r"duplicate entry", r"foreign key", r"integrity",
                              r"\(1062", r"\(1452"]),
    ("OUT_OF_MEMORY", [r"out ?of ?memory", r"heap space"]),
    ("HTTP_5XX", [r"http 5\d\d", r"internal server error", r"bad gateway", r"service unavailable"]),
    ("APPLICATION_EXCEPTION", [r"exception", r"traceback", r"null ?reference", r"null ?pointer"]),
]


def classify_error(message: str) -> str:
    text = (message or "").lower()
    for category, patterns in ERROR_PATTERNS:
        if any(re.search(p, text) for p in patterns):
            return category
    return "UNKNOWN"


# ---------------------------------------------------------------- priority (impact x urgency)
# Impact: how much of the business is affected (1 = high).
# Urgency: how fast it needs fixing (1 = high).
IMPACT_BY_CRITICALITY = {"High": 1, "Medium": 2, "Low": 3}
URGENCY_BY_CATEGORY = {
    "DB_CONNECTION": 1, "OUT_OF_MEMORY": 1,
    "DEADLOCK": 2, "TIMEOUT": 2, "PERMISSION": 2, "MISSING_OBJECT": 2, "HTTP_5XX": 2, "UNKNOWN": 2,
    "SQL_SYNTAX": 3, "CONSTRAINT_VIOLATION": 3, "APPLICATION_EXCEPTION": 3,
}


def calculate_priority(impact: int, urgency: int) -> str:
    """ITIL style matrix: priority number = impact + urgency - 1, kept between 1 and 4."""
    return f"P{min(max(impact + urgency - 1, 1), 4)}"


def severity_for(priority: str) -> str:
    return config.SEVERITY_BY_PRIORITY[priority]


# ---------------------------------------------------------------- SLA
def calculate_deadlines(priority: str, created_at):
    policy = config.SLA_POLICY[priority]
    created = to_dt(created_at)
    return (created + timedelta(minutes=policy["response_minutes"]),
            created + timedelta(minutes=policy["resolution_minutes"]))


def is_open(incident) -> bool:
    return incident["status"] in config.OPEN_STATUSES


def response_breached(incident, now) -> bool:
    """Breached if acknowledged late, or still not acknowledged after the deadline."""
    ack = to_dt(incident.get("acknowledged_at"))
    return (ack or to_dt(now)) > to_dt(incident["response_due"])


def resolution_breached(incident, now) -> bool:
    resolved = to_dt(incident.get("resolved_at"))
    return (resolved or to_dt(now)) > to_dt(incident["resolution_due"])


def resolution_time_used(incident, now) -> float:
    """Share of the resolution window already used (0.0 to 1.0+)."""
    created, due = to_dt(incident["created_at"]), to_dt(incident["resolution_due"])
    total = (due - created).total_seconds()
    end = to_dt(incident.get("resolved_at")) or to_dt(now)
    return (end - created).total_seconds() / total if total else 1.0


def sla_status(incident, now) -> str:
    if not is_open(incident):
        return "Breached" if resolution_breached(incident, now) else "Met"
    if resolution_breached(incident, now) or response_breached(incident, now):
        return "Breached"
    if resolution_time_used(incident, now) >= config.ESCALATION_WARNING_RATIO:
        return "At Risk"
    return "On Track"


# ---------------------------------------------------------------- escalation
def decide_escalation(incident, now):
    """Return (level, reason). Level 0 means no escalation needed."""
    if not is_open(incident):
        return 0, None
    if resolution_breached(incident, now):
        return 2, "Resolution SLA breached"
    if response_breached(incident, now):
        return 1, "Not acknowledged within the response SLA"
    used = resolution_time_used(incident, now)
    if used >= config.ESCALATION_WARNING_RATIO:
        return 1, f"{used:.0%} of the resolution window used"
    if int(incident.get("occurrence_count") or 1) >= config.RECURRENCE_ESCALATION_COUNT:
        return 1, f"Recurring issue ({incident['occurrence_count']} occurrences)"
    return 0, None
