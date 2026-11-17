
import sqlite3
from datetime import datetime
from pathlib import Path

from . import config

TIME_FMT = "%Y-%m-%d %H:%M:%S"
SQL_DIR = config.BASE_DIR / "sql"


# ---------------------------------------------------------------- time helpers
def now() -> datetime:
    return datetime.now().replace(microsecond=0)


def to_str(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime(TIME_FMT)
    return str(value)


def to_dt(value):
    """Accept a datetime or a 'YYYY-MM-DD HH:MM:SS' string and return a datetime."""
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    return datetime.strptime(str(value)[:19], TIME_FMT)


# ---------------------------------------------------------------- connections
def get_connection():
    if config.DB_ENGINE == "mysql":
        import pymysql

        return pymysql.connect(
            **config.MYSQL_CONFIG,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5,
        )
    Path(config.SQLITE_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.SQLITE_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _execute(cursor, sql, params):
    if config.DB_ENGINE == "mysql":
        cursor.execute(sql, params if params else None)
    else:
        cursor.execute(sql.replace("%s", "?"), params or ())


def fetch_all(sql, params=()):
    conn = get_connection()
    try:
        cur = conn.cursor()
        _execute(cur, sql, params)
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_one(sql, params=()):
    rows = fetch_all(sql, params)
    return rows[0] if rows else None


def execute(sql, params=()):
    """Run INSERT/UPDATE/DELETE. Returns the new row id for inserts."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        _execute(cur, sql, params)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def execute_many(sql, rows):
    conn = get_connection()
    try:
        cur = conn.cursor()
        if config.DB_ENGINE == "mysql":
            cur.executemany(sql, rows)
        else:
            cur.executemany(sql.replace("%s", "?"), rows)
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------- schema
TABLES_IN_DROP_ORDER = [
    "log_events", "incident_notes", "job_runs", "incidents",
    "kb_articles", "jobs", "claims", "members",
]


def init_db(reset: bool = False):
    """Create tables (optionally dropping them first) and load seed data."""
    from .seed import seed_reference_data

    schema_file = SQL_DIR / ("schema_mysql.sql" if config.DB_ENGINE == "mysql" else "schema_sqlite.sql")
    statements = [s.strip() for s in schema_file.read_text().split(";") if s.strip()]

    conn = get_connection()
    try:
        cur = conn.cursor()
        if reset:
            if config.DB_ENGINE == "mysql":
                cur.execute("SET FOREIGN_KEY_CHECKS = 0")
            for table in TABLES_IN_DROP_ORDER:
                cur.execute(f"DROP TABLE IF EXISTS {table}")
            if config.DB_ENGINE == "mysql":
                cur.execute("SET FOREIGN_KEY_CHECKS = 1")
        for stmt in statements:
            cur.execute(stmt)
        conn.commit()
    finally:
        conn.close()

    seed_reference_data()
