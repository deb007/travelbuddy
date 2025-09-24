"""Settings utilities for configurable thresholds & trip meta (Settings UI).

Thresholds persisted in metadata table as integer percentages:
  - budget_warn_pct (default 80)
  - budget_danger_pct (default 90)
  - forex_low_pct (default 20)

All values constrained: 1..99 and warn < danger.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict
from app.db.dal import Database

DEFAULT_BUDGET_WARN = 80
DEFAULT_BUDGET_DANGER = 90
DEFAULT_FOREX_LOW = 20

META_KEYS = {
    "budget_warn_pct": DEFAULT_BUDGET_WARN,
    "budget_danger_pct": DEFAULT_BUDGET_DANGER,
    "forex_low_pct": DEFAULT_FOREX_LOW,
}


@dataclass
class Thresholds:
    budget_warn: int
    budget_danger: int
    forex_low: int

    def as_dict(self) -> Dict[str, int]:
        return {
            "budget_warn": self.budget_warn,
            "budget_danger": self.budget_danger,
            "forex_low": self.forex_low,
        }


def _get_metadata_map(db: Database) -> Dict[str, str]:  # lightweight helper
    with db._connect() as conn:  # type: ignore[attr-defined]
        cur = conn.cursor()
        cur.execute(
            "SELECT key, value FROM metadata WHERE key IN (?,?,?)",
            tuple(META_KEYS.keys()),
        )
        return {r[0]: r[1] for r in cur.fetchall()}


def get_thresholds(db: Database) -> Thresholds:
    data = _get_metadata_map(db)

    def _int_or_default(k: str) -> int:
        try:
            return max(1, min(99, int(data.get(k, META_KEYS[k]))))
        except Exception:  # pragma: no cover
            return META_KEYS[k]

    warn = _int_or_default("budget_warn_pct")
    danger = _int_or_default("budget_danger_pct")
    forex_low = _int_or_default("forex_low_pct")
    # Enforce invariants; if invalid stored values, fall back gracefully
    if not (1 <= warn < danger <= 100):
        warn, danger = DEFAULT_BUDGET_WARN, DEFAULT_BUDGET_DANGER
    if not (1 <= forex_low < 100):
        forex_low = DEFAULT_FOREX_LOW
    return Thresholds(warn, danger, forex_low)


def set_thresholds(
    db: Database, budget_warn: int, budget_danger: int, forex_low: int
) -> Thresholds:
    # Basic validation
    if not (1 <= budget_warn < budget_danger <= 100):
        raise ValueError("Invalid budget thresholds: require 1 <= warn < danger <= 100")
    if not (1 <= forex_low < 100):
        raise ValueError("Invalid forex low threshold: 1..99")
    with db._connect() as conn:  # type: ignore[attr-defined]
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO metadata(key,value) VALUES('budget_warn_pct',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=(strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
            (str(budget_warn),),
        )
        cur.execute(
            "INSERT INTO metadata(key,value) VALUES('budget_danger_pct',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=(strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
            (str(budget_danger),),
        )
        cur.execute(
            "INSERT INTO metadata(key,value) VALUES('forex_low_pct',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=(strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
            (str(forex_low),),
        )
    return Thresholds(budget_warn, budget_danger, forex_low)


__all__ = [
    "Thresholds",
    "get_thresholds",
    "set_thresholds",
    "DEFAULT_BUDGET_WARN",
    "DEFAULT_BUDGET_DANGER",
    "DEFAULT_FOREX_LOW",
]
