from datetime import datetime, timedelta

import pytest

from support_monitor import rules

T0 = datetime(2026, 11, 17, 9, 0, 0)


@pytest.mark.parametrize("message,expected", [
    ("(2003, \"Can't connect to MySQL server on 'db-prod-01' (111)\")", "DB_CONNECTION"),
    ("(1064, \"You have an error in your SQL syntax near 'SELEC'\")", "SQL_SYNTAX"),
    ('near "SELEC": syntax error', "SQL_SYNTAX"),
    ("(1146, \"Table 'app_support.pharmacy_claims' doesn't exist\")", "MISSING_OBJECT"),
    ("no such table: pharmacy_claims", "MISSING_OBJECT"),
    ("(1205, 'Lock wait timeout exceeded; try restarting transaction')", "TIMEOUT"),
    ("(1213, 'Deadlock found when trying to get lock')", "DEADLOCK"),
    ("Access denied for user 'svc'@'10.0.0.1'", "PERMISSION"),
    ("OutOfMemoryError: Java heap space", "OUT_OF_MEMORY"),
    ("HTTP 500 Internal Server Error on POST /claims", "HTTP_5XX"),
    ("NullReferenceException in Controller", "APPLICATION_EXCEPTION"),
    ("something odd happened", "UNKNOWN"),
])
def test_classify_error(message, expected):
    assert rules.classify_error(message) == expected


@pytest.mark.parametrize("impact,urgency,expected", [
    (1, 1, "P1"), (1, 2, "P2"), (2, 1, "P2"), (2, 2, "P3"), (1, 3, "P3"), (3, 3, "P4"), (2, 3, "P4"),
])
def test_priority_matrix(impact, urgency, expected):
    assert rules.calculate_priority(impact, urgency) == expected


def _incident(priority="P1", status="New", ack=None, resolved=None, occurrences=1):
    response_due, resolution_due = rules.calculate_deadlines(priority, T0)
    return {"priority": priority, "status": status, "created_at": T0, "acknowledged_at": ack,
            "resolved_at": resolved, "response_due": response_due, "resolution_due": resolution_due,
            "occurrence_count": occurrences}


def test_deadlines_follow_policy():
    response_due, resolution_due = rules.calculate_deadlines("P1", T0)
    assert response_due == T0 + timedelta(minutes=15)
    assert resolution_due == T0 + timedelta(hours=4)


def test_response_breach_when_not_acknowledged():
    inc = _incident("P1")
    assert not rules.response_breached(inc, T0 + timedelta(minutes=10))
    assert rules.response_breached(inc, T0 + timedelta(minutes=16))


def test_on_time_ack_is_not_a_breach_later():
    inc = _incident("P1", status="In Progress", ack=T0 + timedelta(minutes=5))
    assert not rules.response_breached(inc, T0 + timedelta(hours=2))


def test_sla_status_progression():
    inc = _incident("P2", status="In Progress", ack=T0 + timedelta(minutes=5))
    assert rules.sla_status(inc, T0 + timedelta(hours=1)) == "On Track"
    assert rules.sla_status(inc, T0 + timedelta(hours=7)) == "At Risk"
    assert rules.sla_status(inc, T0 + timedelta(hours=9)) == "Breached"


def test_escalation_levels():
    inc = _incident("P1")
    assert rules.decide_escalation(inc, T0 + timedelta(minutes=5)) == (0, None)
    assert rules.decide_escalation(inc, T0 + timedelta(minutes=20))[0] == 1
    assert rules.decide_escalation(inc, T0 + timedelta(hours=5))[0] == 2


def test_recurring_issue_escalates():
    inc = _incident("P4", status="In Progress", ack=T0, occurrences=3)
    level, reason = rules.decide_escalation(inc, T0 + timedelta(minutes=30))
    assert level == 1 and "Recurring" in reason


def test_resolved_incident_never_escalates():
    inc = _incident("P1", status="Resolved", ack=T0, resolved=T0 + timedelta(hours=1))
    assert rules.decide_escalation(inc, T0 + timedelta(days=2)) == (0, None)
