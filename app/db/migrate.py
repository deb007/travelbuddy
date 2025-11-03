"""Database migration utilities.

Handles schema evolution by applying idempotent migrations keyed by an integer
`schema_version` stored in the metadata table. Each migration upgrades the
SQLite schema in-place while preserving user data.
"""

from __future__ import annotations
from pathlib import Path
import sqlite3
import json
from typing import Optional

from . import schema as schema_def
from .schema import init_db

CURRENT_SCHEMA_VERSION = 3
SCHEMA_VERSION_KEY = "schema_version"
LEGACY_TRIP_META_KEYS = ("trip_start_date", "trip_end_date")
DEFAULT_CURRENCIES = ["INR", "SGD", "MYR"]


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
    """Apply required migrations and return resulting schema version."""
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        version = _get_schema_version(conn) or 1
        if version < 2:
            _migrate_to_v2(conn)
            version = 2
        if version < 3:
            _migrate_to_v3(conn)
            version = 3
        _set_schema_version(conn, version)
        conn.commit()
        return version
    finally:
        conn.close()


def _set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO metadata (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
        f"updated_at=({schema_def.BASIC_UTC_NOW})",
        (SCHEMA_VERSION_KEY, str(version)),
    )


def _migrate_to_v2(conn: sqlite3.Connection) -> None:
    """Upgrade schema to version 2 (multi-trip foundation)."""
    conn.execute("PRAGMA foreign_keys=OFF")
    cur = conn.cursor()
    try:
        trip_id = _ensure_trip_record(cur)
        _ensure_active_trip_metadata(cur, trip_id)
        _apply_legacy_trip_dates(cur, trip_id)
        _rebuild_budgets(cur, trip_id)
        _rebuild_forex_cards(cur, trip_id)
        _rebuild_expenses(cur, trip_id)
        _drop_legacy_trip_metadata(cur)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


def _ensure_trip_record(cur: sqlite3.Cursor) -> int:
    """Ensure a trip row exists, returning its id."""
    cur.execute("SELECT id FROM trips ORDER BY id LIMIT 1")
    row = cur.fetchone()
    if row:
        return int(row[0])
    cur.execute(
        """
        INSERT INTO trips (name, status)
        VALUES (?, 'active')
        """,
        ("Legacy Trip",),
    )
    return int(cur.lastrowid)


def _ensure_active_trip_metadata(cur: sqlite3.Cursor, trip_id: int) -> None:
    cur.execute("SELECT value FROM metadata WHERE key = 'active_trip_id'")
    row = cur.fetchone()
    if row:
        return
    cur.execute(
        """
        INSERT INTO metadata (key, value)
        VALUES ('active_trip_id', ?)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = ({now})
        """.format(now=schema_def.BASIC_UTC_NOW),
        (str(trip_id),),
    )


def _apply_legacy_trip_dates(cur: sqlite3.Cursor, trip_id: int) -> None:
    meta = _fetch_legacy_trip_meta(cur)
    if not meta:
        return
    cur.execute("SELECT start_date, end_date FROM trips WHERE id=?", (trip_id,))
    current = cur.fetchone() or (None, None)
    start = meta.get("trip_start_date", current[0])
    end = meta.get("trip_end_date", current[1])
    if start != current[0] or end != current[1]:
        cur.execute(
            f"UPDATE trips SET start_date=?, end_date=?, updated_at=({schema_def.BASIC_UTC_NOW}) WHERE id=?",
            (start, end, trip_id),
        )


def _fetch_legacy_trip_meta(cur: sqlite3.Cursor) -> dict[str, str]:
    cur.execute(
        "SELECT key, value FROM metadata WHERE key IN (?, ?)",
        LEGACY_TRIP_META_KEYS,
    )
    data = cur.fetchall()
    return {row[0]: row[1] for row in data}


def _drop_legacy_trip_metadata(cur: sqlite3.Cursor) -> None:
    cur.execute(
        "DELETE FROM metadata WHERE key IN (?, ?)",
        LEGACY_TRIP_META_KEYS,
    )


def _rebuild_budgets(cur: sqlite3.Cursor, trip_id: int) -> None:
    if not _table_exists(cur, "budgets"):
        cur.execute(schema_def.BUDGETS_DDL)
        cur.execute(schema_def.BUDGETS_TRIP_INDEX_DDL)
        return
    if _column_exists(cur, "budgets", "trip_id"):
        return
    cur.execute("ALTER TABLE budgets RENAME TO budgets_legacy")
    cur.execute(schema_def.BUDGETS_DDL)
    cur.execute(
        """
        INSERT INTO budgets (trip_id, currency, max_amount, spent_amount, updated_at)
        SELECT ?, currency, max_amount, spent_amount, updated_at
        FROM budgets_legacy
        """,
        (trip_id,),
    )
    cur.execute("DROP TABLE budgets_legacy")
    cur.execute(schema_def.BUDGETS_TRIP_INDEX_DDL)


def _rebuild_forex_cards(cur: sqlite3.Cursor, trip_id: int) -> None:
    if not _table_exists(cur, "forex_cards"):
        cur.execute(schema_def.FOREX_CARDS_DDL)
        cur.execute(schema_def.FOREX_TRIP_INDEX_DDL)
        return
    if _column_exists(cur, "forex_cards", "trip_id"):
        return
    cur.execute("ALTER TABLE forex_cards RENAME TO forex_cards_legacy")
    cur.execute(schema_def.FOREX_CARDS_DDL)
    cur.execute(
        """
        INSERT INTO forex_cards (trip_id, currency, loaded_amount, spent_amount, updated_at)
        SELECT ?, currency, loaded_amount, spent_amount, updated_at
        FROM forex_cards_legacy
        """,
        (trip_id,),
    )
    cur.execute("DROP TABLE forex_cards_legacy")
    cur.execute(schema_def.FOREX_TRIP_INDEX_DDL)


def _rebuild_expenses(cur: sqlite3.Cursor, trip_id: int) -> None:
    if not _table_exists(cur, "expenses"):
        cur.execute(schema_def.EXPENSES_DDL)
        cur.execute(schema_def.EXPENSES_TRIP_INDEX_DDL)
        return
    if _column_exists(cur, "expenses", "trip_id"):
        return
    cur.execute("ALTER TABLE expenses RENAME TO expenses_legacy")
    cur.execute(schema_def.EXPENSES_DDL)
    cur.execute(
        """
        INSERT INTO expenses (
            id, trip_id, amount, currency, category, description, date,
            payment_method, inr_equivalent, exchange_rate, created_at, updated_at
        )
        SELECT
            id, ?, amount, currency, category, description, date,
            payment_method, inr_equivalent, exchange_rate, created_at, updated_at
        FROM expenses_legacy
        """,
        (trip_id,),
    )
    cur.execute("DROP TABLE expenses_legacy")
    cur.execute(schema_def.EXPENSES_TRIP_INDEX_DDL)
    _refresh_autoincrement(cur, "expenses", "id")


def _refresh_autoincrement(cur: sqlite3.Cursor, table: str, pk_column: str) -> None:
    cur.execute(f"SELECT MAX({pk_column}) FROM {table}")
    row = cur.fetchone()
    if not row or row[0] is None:
        return
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'"
    )
    if cur.fetchone() is None:
        return
    cur.execute(
        "UPDATE sqlite_sequence SET seq=? WHERE name=?",
        (int(row[0]), table),
    )


def _table_exists(cur: sqlite3.Cursor, name: str) -> bool:
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    )
    return cur.fetchone() is not None


def _column_exists(cur: sqlite3.Cursor, table: str, column: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def _migrate_to_v3(conn: sqlite3.Connection) -> None:
    """Upgrade schema to version 3 (per-trip currencies and global defaults)."""
    cur = conn.cursor()
    try:
        # Add currencies column to trips table if it doesn't exist
        if not _column_exists(cur, "trips", "currencies"):
            cur.execute("ALTER TABLE trips ADD COLUMN currencies TEXT")

            # Set default currencies for all existing trips
            default_currencies_json = json.dumps(DEFAULT_CURRENCIES)
            cur.execute(
                f"UPDATE trips SET currencies = ?, updated_at = ({schema_def.BASIC_UTC_NOW}) WHERE currencies IS NULL",
                (default_currencies_json,),
            )

        # Add global default_currencies setting if not exists
        cur.execute("SELECT value FROM metadata WHERE key = 'default_currencies'")
        if not cur.fetchone():
            cur.execute(
                f"""
                INSERT INTO metadata (key, value, updated_at)
                VALUES ('default_currencies', ?, ({schema_def.BASIC_UTC_NOW}))
                """,
                (json.dumps(DEFAULT_CURRENCIES),),
            )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
