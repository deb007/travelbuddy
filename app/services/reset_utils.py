"""Utilities to reset trip data for starting a new trip.

The reset operation removes transactional data while optionally preserving
application-level configuration (thresholds, provider overrides, UI prefs).

Data removed:
  - expenses
  - budgets (spent & max) (optionally preserved?) -> we clear by default
  - forex_cards
  - exchange_rates
  - metadata keys: trip_* (dates) and any rate overrides (NOT global settings if preserve_settings True)

If preserve_settings is True we keep:
  - threshold keys: budget_warn_pct, budget_danger_pct, forex_low_pct
  - custom settings keys (exchange_rate_provider_override, rates_cache_ttl, budget_* ui_* widget_* default_budget_amounts)
Else metadata table is fully cleared except maybe schema_version if used.

A lightweight safeguard requires a caller-provided confirmation flag before execution.
"""

from __future__ import annotations
from typing import Iterable

PRESERVE_META_PREFIXES: Iterable[str] = (
    "budget_warn_pct",
    "budget_danger_pct",
    "forex_low_pct",
    "exchange_rate_provider_override",
    "rates_cache_ttl",
    "budget_enforce_cap",
    "budget_auto_create",
    "default_budget_amounts",
    "ui_theme",
    "ui_show_day_totals",
    "ui_expense_layout",
    "widget_show_",  # prefix
)

TRIP_META_PREFIXES: Iterable[str] = (
    "trip_start_date",
    "trip_end_date",
)


def _should_preserve(key: str) -> bool:
    for p in PRESERVE_META_PREFIXES:
        if p.endswith("_"):
            if key.startswith(p):
                return True
        elif key == p:
            return True
    return False


def reset_trip_data(db, preserve_settings: bool) -> None:
    with db._connect() as conn:  # type: ignore[attr-defined]
        cur = conn.cursor()
        # Delete transactional tables
        cur.execute("DELETE FROM expenses")
        cur.execute("DELETE FROM budgets")
        cur.execute("DELETE FROM forex_cards")
        cur.execute("DELETE FROM exchange_rates")
        # Metadata handling
        if preserve_settings:
            # Load existing metadata and reinsert only preserved keys
            cur.execute("SELECT key,value FROM metadata")
            rows = cur.fetchall()
            keep = [(r["key"], r["value"]) for r in rows if _should_preserve(r["key"])]
            # Clear all
            cur.execute("DELETE FROM metadata")
            for k, v in keep:
                cur.execute(
                    "INSERT INTO metadata(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=(strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
                    (k, v),
                )
        else:
            cur.execute("DELETE FROM metadata")
        conn.commit()


__all__ = ["reset_trip_data"]
