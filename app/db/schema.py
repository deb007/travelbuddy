"""Database schema DDL definitions and initialization utilities for MVP.

Tables:
  - budgets: per-currency max & spent values
  - forex_cards: loaded and spent tracking for foreign currencies
  - exchange_rates: cached rates (base INR) with timestamp
  - expenses: individual expense records
  - metadata: key/value store (trip dates etc.)
"""

from __future__ import annotations
import sqlite3
from typing import Sequence
from pathlib import Path

BUDGETS_DDL = """
CREATE TABLE IF NOT EXISTS budgets (
    currency TEXT PRIMARY KEY, -- 'INR' | 'SGD' | 'MYR'
    max_amount REAL NOT NULL DEFAULT 0,
    spent_amount REAL NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
"""

FOREX_CARDS_DDL = """
CREATE TABLE IF NOT EXISTS forex_cards (
    currency TEXT PRIMARY KEY, -- 'SGD' | 'MYR'
    loaded_amount REAL NOT NULL DEFAULT 0,
    spent_amount REAL NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
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

EXPENSES_DDL = """
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    amount REAL NOT NULL,
    currency TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT,
    date TEXT NOT NULL, -- ISO date (YYYY-MM-DD)
    payment_method TEXT NOT NULL, -- 'cash' | 'forex' | 'card'
    inr_equivalent REAL NOT NULL,
    exchange_rate REAL NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
"""

METADATA_DDL = """
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
"""

DDL_ORDER: Sequence[str] = (
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
        conn.commit()
    finally:
        conn.close()
