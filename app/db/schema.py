"""Database schema DDL definitions and initialization utilities for MVP.

Tables:
  - trips: high-level trip records (enables multi-trip support)
  - budgets: per-currency max & spent values (scoped per trip)
  - forex_cards: loaded and spent tracking for foreign currencies (scoped per trip)
  - exchange_rates: cached rates (base INR) with timestamp
  - expenses: individual expense records
  - metadata: key/value store (trip dates etc.) and active trip marker
"""

from __future__ import annotations
import sqlite3
from typing import Sequence
from pathlib import Path

BASIC_UTC_NOW = "strftime('%Y-%m-%dT%H:%M:%fZ','now')"

TRIPS_DDL = f"""
CREATE TABLE IF NOT EXISTS trips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    start_date TEXT,
    end_date TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived')),
    created_at TEXT NOT NULL DEFAULT ({BASIC_UTC_NOW}),
    updated_at TEXT NOT NULL DEFAULT ({BASIC_UTC_NOW})
);
"""

BUDGETS_DDL = f"""
CREATE TABLE IF NOT EXISTS budgets (
    trip_id INTEGER NOT NULL,
    currency TEXT NOT NULL, -- 'INR' | 'SGD' | 'MYR'
    max_amount REAL NOT NULL DEFAULT 0,
    spent_amount REAL NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT ({BASIC_UTC_NOW}),
    PRIMARY KEY (trip_id, currency),
    FOREIGN KEY (trip_id) REFERENCES trips(id) ON DELETE CASCADE
);
"""

FOREX_CARDS_DDL = f"""
CREATE TABLE IF NOT EXISTS forex_cards (
    trip_id INTEGER NOT NULL,
    currency TEXT NOT NULL, -- 'SGD' | 'MYR'
    loaded_amount REAL NOT NULL DEFAULT 0,
    spent_amount REAL NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT ({BASIC_UTC_NOW}),
    PRIMARY KEY (trip_id, currency),
    FOREIGN KEY (trip_id) REFERENCES trips(id) ON DELETE CASCADE
);
"""

EXCHANGE_RATES_DDL = """
CREATE TABLE IF NOT EXISTS exchange_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    base_currency TEXT NOT NULL, -- 'INR'
    quote_currency TEXT NOT NULL, -- 'SGD','MYR'
    rate REAL NOT NULL,
    fetched_at TEXT NOT NULL, -- ISO timestamp
    UNIQUE(base_currency, quote_currency)
);
"""

EXPENSES_DDL = f"""
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    currency TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT,
    date TEXT NOT NULL, -- ISO date (YYYY-MM-DD)
    payment_method TEXT NOT NULL, -- 'cash' | 'forex' | 'card'
    inr_equivalent REAL NOT NULL,
    exchange_rate REAL NOT NULL,
    created_at TEXT NOT NULL DEFAULT ({BASIC_UTC_NOW}),
    updated_at TEXT NOT NULL DEFAULT ({BASIC_UTC_NOW}),
    FOREIGN KEY (trip_id) REFERENCES trips(id) ON DELETE CASCADE
);
"""

METADATA_DDL = f"""
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT ({BASIC_UTC_NOW})
);
"""

TRIPS_STATUS_INDEX_DDL = "CREATE INDEX IF NOT EXISTS idx_trips_status ON trips(status);"
BUDGETS_TRIP_INDEX_DDL = "CREATE INDEX IF NOT EXISTS idx_budgets_trip ON budgets(trip_id);"
FOREX_TRIP_INDEX_DDL = "CREATE INDEX IF NOT EXISTS idx_forex_trip ON forex_cards(trip_id);"
EXPENSES_TRIP_INDEX_DDL = (
    "CREATE INDEX IF NOT EXISTS idx_expenses_trip_date ON expenses(trip_id, date);"
)
METADATA_ACTIVE_TRIP_INDEX_DDL = """
CREATE INDEX IF NOT EXISTS idx_metadata_active_trip
ON metadata(key)
WHERE key = 'active_trip_id';
"""

DDL_ORDER: Sequence[str] = (
    TRIPS_DDL,
    BUDGETS_DDL,
    FOREX_CARDS_DDL,
    EXCHANGE_RATES_DDL,
    EXPENSES_DDL,
    METADATA_DDL,
)


def init_db(path: Path) -> None:
    """Create all tables idempotently.

    Parameters
    ----------
    path: Path to SQLite database file.
    """
    conn = sqlite3.connect(path)
    try:
        cur = conn.cursor()
        for ddl in DDL_ORDER:
            cur.execute(ddl)
        trip_id = _ensure_default_trip(cur)
        _ensure_active_trip_metadata(cur, trip_id)
        _ensure_indexes(cur)
        conn.commit()
    finally:
        conn.close()


def _ensure_default_trip(cur: sqlite3.Cursor) -> int:
    """Ensure a baseline trip record exists and return its id."""
    cur.execute("SELECT id FROM trips ORDER BY id LIMIT 1")
    row = cur.fetchone()
    if row:
        return int(row[0])
    cur.execute(
        """
        INSERT INTO trips (name, status)
        VALUES (?, 'active')
        """,
        ("Default Trip",),
    )
    return int(cur.lastrowid)


def _ensure_active_trip_metadata(cur: sqlite3.Cursor, trip_id: int) -> None:
    """Ensure metadata references an active trip id for legacy installs."""
    cur.execute("SELECT value FROM metadata WHERE key = 'active_trip_id'")
    row = cur.fetchone()
    if row:
        return
    cur.execute(
        """
        INSERT INTO metadata (key, value)
        VALUES ('active_trip_id', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value,
            updated_at = ({})
        """.format(BASIC_UTC_NOW),
        (str(trip_id),),
    )


def _ensure_indexes(cur: sqlite3.Cursor) -> None:
    """Create indexes, tolerating legacy schemas missing scoped columns."""
    for ddl in (
        TRIPS_STATUS_INDEX_DDL,
        BUDGETS_TRIP_INDEX_DDL,
        FOREX_TRIP_INDEX_DDL,
        EXPENSES_TRIP_INDEX_DDL,
        METADATA_ACTIVE_TRIP_INDEX_DDL,
    ):
        try:
            cur.execute(ddl)
        except sqlite3.OperationalError:
            # Legacy tables may lack columns; migration handles re-creation.
            continue
