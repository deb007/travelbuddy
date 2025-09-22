"""Simple bootstrap migration utilities for MVP.

For the MVP we only need idempotent creation of the schema defined in `schema.py`.
We also store a `schema_version` key inside the metadata table so future
iterations can add conditional migrations.

Design notes:
- Single function `apply_migrations(db_path: Path)` that ensures tables exist.
- Writes metadata key `schema_version` with current integer (1) if absent.
- Safe to call multiple times (idempotent).
"""

from __future__ import annotations
from pathlib import Path
import sqlite3
from typing import Optional

from .schema import init_db

CURRENT_SCHEMA_VERSION = 1
SCHEMA_VERSION_KEY = "schema_version"


def _get_schema_version(conn: sqlite3.Connection) -> Optional[int]:
    try:
        cur = conn.cursor()
        cur.execute("SELECT value FROM metadata WHERE key=?", (SCHEMA_VERSION_KEY,))
        row = cur.fetchone()
        if row:
            return int(row[0])
    except sqlite3.OperationalError:
        # metadata table may not exist yet (first run before init_db)
        return None
    return None


def apply_migrations(db_path: Path) -> int:
    """Apply required migrations and return resulting schema version.

    Steps:
    1. Ensure all base tables exist via init_db().
    2. Ensure metadata has schema_version row.
    3. (Future) Conditional blocks for version upgrades.
    """
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        version = _get_schema_version(conn)
        if version is None:
            cur.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                (SCHEMA_VERSION_KEY, str(CURRENT_SCHEMA_VERSION)),
            )
            conn.commit()
            version = CURRENT_SCHEMA_VERSION
        # Placeholder for future migrations:
        # if version < 2:
        #     ... perform changes ...
        return version
    finally:
        conn.close()
