"""Seeding helpers for initial budget rows (T03.01).

Provides a simple function `seed_budgets` that ensures baseline budget
rows exist for the three currencies used in the MVP. Existing rows are
left untouched so this can be safely re-run.
"""

from __future__ import annotations
from pathlib import Path
import sqlite3
from typing import Mapping

from .schema import init_db

DEFAULT_MAX_AMOUNTS = {
    "INR": 0.0,  # Caller may override
    "SGD": 0.0,
    "MYR": 0.0,
}


def seed_budgets(db_path: Path, max_amounts: Mapping[str, float] | None = None) -> None:
    init_db(db_path)  # ensure tables exist
    overrides = max_amounts or {}
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        for currency, default_max in DEFAULT_MAX_AMOUNTS.items():
            max_val = overrides.get(currency, default_max)
            # Insert row if not present; do not modify existing budgets (user controlled)
            cur.execute(
                "INSERT OR IGNORE INTO budgets (currency, max_amount, spent_amount) VALUES (?, ?, 0)",
                (currency, float(max_val)),
            )
        conn.commit()
