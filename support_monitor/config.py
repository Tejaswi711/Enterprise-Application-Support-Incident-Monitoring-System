
import os
from pathlib import Path

try:  # python-dotenv is optional
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------- database
# "sqlite" runs with zero setup. Set DB_ENGINE=mysql to use a MySQL server.
DB_ENGINE = os.getenv("DB_ENGINE", "sqlite").lower()
SQLITE_PATH = os.getenv("SQLITE_PATH", str(DATA_DIR / "app_support.db"))
MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "support_user"),
    "password": os.getenv("MYSQL_PASSWORD", "support_pass"),
    "database": os.getenv("MYSQL_DATABASE", "app_support"),
}

# ---------------------------------------------------------------- logs
APP_LOG_FILE = Path(os.getenv("APP_LOG_FILE", str(LOG_DIR / "application.log")))
JOB_LOG_FILE = Path(os.getenv("JOB_LOG_FILE", str(LOG_DIR / "job_runs.log")))
ANALYZER_STATE_FILE = Path(os.getenv("ANALYZER_STATE_FILE", str(DATA_DIR / "log_offset.txt")))

# ---------------------------------------------------------------- SLA policy
# Response = time to acknowledge. Resolution = time to resolve.
SLA_POLICY = {
    "P1": {"response_minutes": 15, "resolution_minutes": 240},    # 15 min / 4 h
    "P2": {"response_minutes": 30, "resolution_minutes": 480},    # 30 min / 8 h
    "P3": {"response_minutes": 240, "resolution_minutes": 1440},  # 4 h / 24 h
    "P4": {"response_minutes": 480, "resolution_minutes": 4320},  # 8 h / 72 h
}
SEVERITY_BY_PRIORITY = {"P1": "Critical", "P2": "High", "P3": "Medium", "P4": "Low"}

OPEN_STATUSES = ("New", "In Progress", "On Hold")
CLOSED_STATUSES = ("Resolved", "Closed")

# ---------------------------------------------------------------- escalation
ESCALATION_WARNING_RATIO = 0.75     # escalate when 75% of the resolution window is used
RECURRENCE_ESCALATION_COUNT = 3     # escalate when the same problem repeats 3+ times
ESCALATION_TARGETS = {
    1: "Team Lead, Application Support",
    2: "Support Manager / Major Incident Manager",
}

# ---------------------------------------------------------------- log monitor
LOG_ERROR_THRESHOLD = 3   # same ERROR this many times in one scan -> incident
COMPONENT_CRITICALITY = {
    "claims-api": "High",
    "billing-service": "High",
    "auth-service": "High",
    "member-portal": "Medium",
    "notification-service": "Low",
}
