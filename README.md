# Enterprise Application Support Monitoring System

A Python and SQL-based application support monitoring system that simulates database job monitoring, analyzes application logs, automatically creates incidents, tracks Service Level Agreements (SLAs), and escalates unresolved issues.

## Project Overview

Application support teams need to identify application failures, investigate errors, manage incidents, and resolve issues within defined SLA timelines.

This project demonstrates an automated monitoring workflow that detects database job failures and application log errors, classifies issues, creates incidents, and tracks their resolution.

## Key Features

- **Database Job Monitoring:** Executes scheduled SQL jobs and records execution results.
- **Application Log Monitoring:** Reads and analyzes application logs to identify errors and critical events.
- **Error Classification:** Categorizes errors such as database connection failures, SQL syntax errors, deadlocks, timeouts, and application exceptions.
- **Automated Incident Management:** Creates incidents automatically when failures are detected and updates existing incidents when recurring issues occur.
- **Priority Assignment:** Assigns incident priorities based on business impact and urgency.
- **SLA Tracking:** Monitors response and resolution deadlines.
- **Incident Escalation:** Escalates unresolved and recurring incidents based on configured rules.
- **Incident Lifecycle Management:** Supports incident acknowledgement, assignment, resolution, and work notes.
- **Monitoring Reports:** Generates summary metrics for incidents, job execution, SLA compliance, and resolution time.

## Technology Stack

| Technology | Usage |
|---|---|
| Python | Application logic and automation |
| SQL | Database queries and operations |
| SQLite | Default database |
| MySQL | Optional database configuration |
| Flask | REST API integration, where configured |
| Pytest | Automated testing |
| Logging | Application and job log monitoring |

## Project Structure

```text
app-support-monitor/
│
├── support_monitor/
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py
│   ├── db.py
│   ├── incidents.py
│   ├── job_monitor.py
│   ├── log_monitor.py
│   ├── monitor.py
│   ├── rules.py
│   └── seed.py
│
├── tests/
│   ├── test_rules.py
│   └── test_end_to_end.py
│
├── sql/
│   ├── schema_sqlite.sql
│   └── schema_mysql.sql
│
├── logs/
├── data/
├── requirements.txt
├── .gitignore
└── README.md
```

*Note: Adjust the structure above if your actual repository uses different filenames or folders.*

## Installation and Setup

### 1. Clone the repository

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
cd app-support-monitor
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

Activate it on Windows:

```powershell
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Initialize the database

```bash
python -m support_monitor.cli init-db
```

### 5. View available commands

```bash
python -m support_monitor.cli --help
```

## Running the Project

Run the demonstration:

```bash
python -m support_monitor.demo
```

Generate a monitoring report:

```bash
python -m support_monitor.cli report
```

Run the monitoring workflow:

```bash
python -m support_monitor.cli monitor
```

Other available operations include:

- `init-db` – Initialize database tables.
- `seed-demo` – Load demonstration data.
- `run-jobs` – Execute database jobs.
- `simulate-logs` – Generate sample application logs.
- `analyze-logs` – Analyze application logs.
- `check-sla` – Check SLA deadlines.
- `list` – List incidents.
- `show` – View incident details.
- `ack` – Acknowledge an incident.
- `resolve` – Resolve an incident.
- `fix-job` – Update a job's SQL query.
- `report` – Generate monitoring metrics.

## Monitoring Workflow

1. Execute scheduled database jobs.
2. Record successful and failed job executions.
3. Generate and analyze application logs.
4. Identify and classify errors.
5. Automatically create or update incidents.
6. Assign incident priority based on impact and urgency.
7. Track response and resolution SLA deadlines.
8. Escalate incidents when configured conditions are met.
9. Acknowledge and resolve incidents.
10. Generate monitoring reports.

## Incident Priority and SLA Management

The system uses impact and urgency to calculate incident priority.

| Priority | Severity | Response SLA | Resolution SLA |
|---|---|---:|---:|
| P1 | Critical | 15 minutes | 4 hours |
| P2 | High | 30 minutes | 8 hours |
| P3 | Medium | 4 hours | 24 hours |
| P4 | Low | 8 hours | 72 hours |

These SLA values are configurable in the project.

## Testing

The project includes unit tests and end-to-end tests using Pytest.

Run all tests:

```bash
python -m pytest -v
```

Run rule tests:

```bash
python -m pytest tests/test_rules.py -v
```

Run end-to-end tests:

```bash
python -m pytest tests/test_end_to_end.py -v
```

### Test Results

- Rule tests: **26 passed**
- End-to-end tests: **3 passed**
- Total: **29 tests passed**

The tests cover error classification, priority calculation, SLA deadlines, escalation rules, incident lifecycle, job failure handling, and log analysis.

## Sample Monitoring Metrics

Example output from the demonstration:

| Metric | Sample Result |
|---|---:|
| Open Incidents | 8 |
| Resolved Incidents | 39 |
| Job Runs (24 hours) | 36 |
| Failed Jobs (24 hours) | 14 |
| Job Success Rate | 61.1% |
| SLA Compliance | 76.9% |
| Mean Time to Resolution | 352.4 minutes |

*Note: These are simulated demonstration results, not live production monitoring metrics.*

## Learning Outcomes

Through this project, I practised:

- Python application development and modular programming.
- SQL queries, database operations, and data persistence.
- Application and job log analysis.
- Error handling and exception management.
- Incident lifecycle management.
- SLA monitoring and escalation logic.
- Automated testing using Pytest.
- Troubleshooting simulated application and database failures.

## Future Enhancements

- Develop a web-based monitoring dashboard.
- Integrate real-time email and alert notifications.
- Add authentication and role-based access control.
- Integrate with external incident management platforms.
- Add live MySQL server monitoring.
- Implement scheduled background monitoring.

## Author

**Tejaswi Siddagoni**

