from sqlmodel import SQLModel, create_engine, Session as DBSession
from sqlalchemy.pool import StaticPool
from config import settings
from models.session_model import Session
import sqlite3
import logging

logger = logging.getLogger(__name__)

# Create engine with connection pooling
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


def create_db_and_tables():
    """Create database and tables"""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Get database session"""
    with DBSession(engine) as session:
        yield session


def run_migrations():
    """
    Run lightweight, idempotent migrations (e.g., add cos_key column).
    """
    # Only handle SQLite path migrations
    if not settings.database_url.startswith("sqlite:///"):
        logger.info("Migration skipped: non-sqlite database_url")
        return

    db_path = settings.database_url.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    try:
        table_name = Session.__tablename__ or "sessions"
        # Resolve real table name if different
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND (name=? OR name LIKE '%session%')",
            (table_name,),
        )
        rows = [r[0] for r in cur.fetchall()]
        if not rows:
            logger.warning("Migration: session table not found, skip")
            return
        real_table = table_name if table_name in rows else rows[0]

        cur = conn.execute(f'PRAGMA table_info("{real_table}")')
        cols = [r[1] for r in cur.fetchall()]
        if "cos_key" not in cols:
            conn.execute(f'ALTER TABLE "{real_table}" ADD COLUMN cos_key TEXT')
            conn.commit()
            logger.info(f"Migration: added cos_key to {real_table}")

        # Re-read columns for user_id migration
        cur = conn.execute(f'PRAGMA table_info("{real_table}")')
        cols = [r[1] for r in cur.fetchall()]
        if "user_id" not in cols:
            conn.execute(f'ALTER TABLE "{real_table}" ADD COLUMN user_id INTEGER')
            conn.commit()
            logger.info(f"Migration: added user_id to {real_table}")
        # --- devices.user_id: NOT NULL → nullable ---
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='devices'")
        if cur.fetchone():
            cur = conn.execute("PRAGMA table_info('devices')")
            dev_cols = {r[1]: r for r in cur.fetchall()}
            if 'user_id' in dev_cols and dev_cols['user_id'][3]:  # [3] = notnull flag
                conn.execute("""
                    CREATE TABLE devices_tmp (
                        id INTEGER PRIMARY KEY,
                        device_id TEXT NOT NULL UNIQUE,
                        user_id INTEGER,
                        name TEXT DEFAULT '',
                        is_online BOOLEAN DEFAULT 0,
                        last_seen TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.execute("INSERT INTO devices_tmp SELECT * FROM devices")
                conn.execute("DROP TABLE devices")
                conn.execute("ALTER TABLE devices_tmp RENAME TO devices")
                conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_devices_device_id ON devices(device_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS ix_devices_user_id ON devices(user_id)")
                conn.commit()
                logger.info("Migration: made devices.user_id nullable")

    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
    finally:
        conn.close()
