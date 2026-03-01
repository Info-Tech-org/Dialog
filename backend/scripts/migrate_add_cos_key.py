"""
SQLite migration: add cos_key column to session table (name auto-detected).
Idempotent: if column exists or table missing, does nothing.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("familymvp.db")


def table_has_column(conn: sqlite3.Connection, table_name: str, column: str) -> bool:
    cur = conn.execute(f'PRAGMA table_info("{table_name}")')
    cols = [row[1] for row in cur.fetchall()]
    return column in cols


def get_session_table_name(conn: sqlite3.Connection) -> str | None:
    # Prefer exact match "sessions", fallback to first table containing "session"
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND (name='sessions' OR name LIKE '%session%')"
    )
    rows = [r[0] for r in cur.fetchall()]
    if not rows:
        return None
    if "sessions" in rows:
        return "sessions"
    return rows[0]


def migrate(db_path: Path = DB_PATH):
    if not db_path.exists():
        print(f"[migrate] DB not found: {db_path}, skip.")
        return

    conn = sqlite3.connect(str(db_path))
    try:
        table = get_session_table_name(conn)
        if not table:
            print("[migrate] session table not found, skip.")
            return

        if table_has_column(conn, table, "cos_key"):
            print("[migrate] cos_key already exists, skip.")
            return

        conn.execute(f'ALTER TABLE "{table}" ADD COLUMN cos_key TEXT')
        conn.commit()
        print(f"[migrate] Added cos_key column to table {table}.")
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
