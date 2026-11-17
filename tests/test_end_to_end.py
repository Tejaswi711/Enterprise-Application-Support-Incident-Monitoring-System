import random

import pytest

from support_monitor import config, db, incidents, job_monitor, log_monitor


@pytest.fixture(autouse=True)
def temp_env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_ENGINE", "sqlite")
    monkeypatch.setattr(config, "SQLITE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(config, "APP_LOG_FILE", tmp_path / "application.log")
    monkeypatch.setattr(config, "ANALYZER_STATE_FILE", tmp_path / "offset.txt")
    db.init_db(reset=True)


def test_broken_jobs_create_incidents_and_dedupe():
    rng = random.Random(1)
    for job in job_monitor.get_jobs():
        db.execute("UPDATE jobs SET failure_rate = 0 WHERE job_id = %s", (job["job_id"],))

    first = job_monitor.run_all_jobs(rng=rng)
    failed = {r["job_name"]: r for r in first if r["status"] == "FAILED"}
    assert set(failed) == {"pharmacy_rx_extract", "weekly_provider_report"}
    assert failed["pharmacy_rx_extract"]["error_category"] == "MISSING_OBJECT"
    assert failed["weekly_provider_report"]["error_category"] == "SQL_SYNTAX"

    job_monitor.run_all_jobs(rng=rng)
    open_inc = incidents.list_incidents(open_only=True)
    assert len(open_inc) == 2                       # second run did not create duplicates
    assert all(i["occurrence_count"] == 2 for i in open_inc)


def test_incident_lifecycle_and_notes():
    iid, new = incidents.raise_incident("Test", "Can't connect to MySQL server", "MANUAL", "manual:test",
                                        "DB_CONNECTION", impact=1, urgency=1)
    assert new
    inc = incidents.get_incident(iid, with_notes=True)
    assert inc["priority"] == "P1" and inc["incident_number"] == f"INC{100000 + iid}"
    assert any(n["note_type"] == "TROUBLESHOOTING" for n in inc["notes"])   # KB steps attached

    incidents.acknowledge(iid, "analyst")
    done = incidents.resolve(iid, "DB restarted", "Pool exhausted, restarted", "analyst")
    assert done["status"] == "Resolved" and done["resolution_breached"] == 0


def test_log_analysis_reads_only_new_lines():
    path = config.APP_LOG_FILE
    lines = [f"2026-11-17 10:0{i}:00 ERROR [claims-api] HTTP 500 Internal Server Error request_id={i}" for i in range(4)]
    path.write_text("\n".join(lines + ["2026-11-17 10:05:00 INFO [claims-api] ok", "garbage line"]) + "\n")

    res = log_monitor.analyze_logs()
    assert res["levels"]["ERROR"] == 4 and res["levels"]["UNPARSED"] == 1
    assert res["incidents_created"] == 1
    assert res["groups"][0]["count"] == 4           # request ids normalised into one signature

    assert log_monitor.analyze_logs()["lines_read"] == 0   # nothing new since last scan
