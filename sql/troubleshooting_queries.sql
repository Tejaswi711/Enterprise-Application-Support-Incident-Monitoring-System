-- =====================================================================
-- SQL troubleshooting and reporting queries (MySQL 8 syntax)
-- Run in MySQL Workbench / mysql CLI against the app_support database.
-- =====================================================================

-- 1. Failed jobs in the last 24 hours, newest first
SELECT j.job_name, r.started_at, r.error_category, r.error_message, i.incident_number
FROM job_runs r
JOIN jobs j ON j.job_id = r.job_id
LEFT JOIN incidents i ON i.incident_id = r.incident_id
WHERE r.status = 'FAILED'
  AND r.started_at >= NOW() - INTERVAL 24 HOUR
ORDER BY r.started_at DESC;

-- 2. Failure rate per job (which jobs are the least reliable?)
SELECT j.job_name,
       COUNT(*)                                             AS total_runs,
       SUM(r.status = 'FAILED')                             AS failed_runs,
       ROUND(100 * SUM(r.status = 'FAILED') / COUNT(*), 1)  AS failure_pct,
       ROUND(AVG(r.duration_ms) / 1000, 1)                  AS avg_duration_sec
FROM job_runs r
JOIN jobs j ON j.job_id = r.job_id
GROUP BY j.job_name
ORDER BY failure_pct DESC;

-- 3. Most common error categories across jobs
SELECT error_category, COUNT(*) AS occurrences
FROM job_runs
WHERE status = 'FAILED'
GROUP BY error_category
ORDER BY occurrences DESC;

-- 4. Open incidents with age and SLA position
SELECT incident_number, priority, status, title,
       TIMESTAMPDIFF(MINUTE, created_at, NOW())      AS age_minutes,
       TIMESTAMPDIFF(MINUTE, NOW(), resolution_due)  AS minutes_to_resolution_due,
       CASE
           WHEN NOW() > resolution_due THEN 'Resolution breached'
           WHEN acknowledged_at IS NULL AND NOW() > response_due THEN 'Response breached'
           ELSE 'Within SLA'
       END AS sla_position
FROM incidents
WHERE status IN ('New', 'In Progress', 'On Hold')
ORDER BY priority, created_at;

-- 5. SLA compliance by priority for resolved incidents
SELECT priority,
       COUNT(*)                                                    AS resolved,
       SUM(resolution_breached = 0)                                AS met_sla,
       ROUND(100 * SUM(resolution_breached = 0) / COUNT(*), 1)     AS compliance_pct,
       ROUND(AVG(TIMESTAMPDIFF(MINUTE, created_at, resolved_at)))  AS mttr_minutes,
       ROUND(AVG(TIMESTAMPDIFF(MINUTE, created_at, acknowledged_at))) AS mtta_minutes
FROM incidents
WHERE status IN ('Resolved', 'Closed')
GROUP BY priority
ORDER BY priority;

-- 6. Incidents that need escalation right now
SELECT incident_number, priority, title, escalation_level, occurrence_count, assigned_group
FROM incidents
WHERE status IN ('New', 'In Progress', 'On Hold')
  AND (NOW() > resolution_due
       OR (acknowledged_at IS NULL AND NOW() > response_due)
       OR occurrence_count >= 3)
ORDER BY priority, escalation_level DESC;

-- 7. Recurring problems (candidates for a problem ticket / root cause analysis)
SELECT source_ref, error_category, COUNT(*) AS incidents, SUM(occurrence_count) AS total_occurrences
FROM incidents
GROUP BY source_ref, error_category
HAVING SUM(occurrence_count) >= 3
ORDER BY total_occurrences DESC;

-- 8. Log errors per component per hour (spot spikes)
SELECT component, DATE_FORMAT(log_timestamp, '%Y-%m-%d %H:00') AS hour_bucket, COUNT(*) AS errors
FROM log_events
GROUP BY component, hour_bucket
ORDER BY hour_bucket DESC, errors DESC;

-- 9. Full timeline of one incident (change the number)
SELECT n.created_at, n.note_type, n.author, n.note_text
FROM incident_notes n
JOIN incidents i ON i.incident_id = n.incident_id
WHERE i.incident_number = 'INC100001'
ORDER BY n.created_at;

-- 10. Analyst workload
SELECT COALESCE(assigned_to, 'Unassigned') AS analyst,
       SUM(status IN ('New', 'In Progress', 'On Hold')) AS open_items,
       SUM(status = 'Resolved') AS resolved_items
FROM incidents
GROUP BY analyst
ORDER BY open_items DESC;

-- ---------------------------------------------------------------------
-- Live database health checks used while troubleshooting a job failure
-- ---------------------------------------------------------------------
SHOW FULL PROCESSLIST;                                 -- long running / blocking sessions
SHOW STATUS LIKE 'Threads_connected';                  -- current connections
SHOW VARIABLES LIKE 'max_connections';                 -- connection limit
SELECT * FROM performance_schema.data_lock_waits;      -- who is blocking whom
SHOW ENGINE INNODB STATUS;                             -- latest deadlock details
EXPLAIN SELECT * FROM claims WHERE member_id = 1001;   -- check index usage
