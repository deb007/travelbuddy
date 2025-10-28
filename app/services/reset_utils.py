"""Utilities to reset trip data for starting a new trip.

The reset operation removes transactional data while optionally preserving
application-level configuration (thresholds, provider overrides, UI prefs).

By default the reset targets only the active trip's transactional data, leaving
global settings in place. Callers can request a full wipe (all trips and
metadata) via the `wipe_all` flag if they explicitly need a clean slate.
"""

from __future__ import annotations
from typing import Iterable, Optional

from app.services.trip_context import get_active_trip_id

UTC_NOW_SQL = "strftime('%Y-%m-%dT%H:%M:%fZ','now')"

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


def reset_trip_data(
    db,
    preserve_settings: bool,
    trip_id: Optional[int] = None,
    wipe_all: bool = False,
) -> None:
    """Reset trip data.

    Parameters
    ----------
    db: Database instance (duck-typed).
    preserve_settings: bool
        Preserve metadata keys related to configuration when wiping all trips.
    trip_id: Optional[int]
        Target trip. Defaults to active trip when not provided.
    wipe_all: bool
        When True, remove data for every trip (legacy behaviour).
    """
    with db._connect() as conn:  # type: ignore[attr-defined]
        cur = conn.cursor()
        if wipe_all:
            _wipe_all(cur, preserve_settings)
        else:
            target_trip = trip_id if trip_id is not None else get_active_trip_id(db)
            _reset_single_trip(cur, target_trip)
        conn.commit()


def _reset_single_trip(cur, trip_id: int) -> None:
    """Remove transactional data for a single trip."""
    cur.execute("DELETE FROM expenses WHERE trip_id = ?", (trip_id,))
    cur.execute("DELETE FROM budgets WHERE trip_id = ?", (trip_id,))
    cur.execute("DELETE FROM forex_cards WHERE trip_id = ?", (trip_id,))
    # Exchange rates are global; leave untouched.
    cur.execute(
        f"""
        UPDATE trips
        SET start_date = NULL,
            end_date = NULL,
            updated_at = ({UTC_NOW_SQL})
        WHERE id = ?
        """,
        (trip_id,),
    )


def _wipe_all(cur, preserve_settings: bool) -> None:
    """Remove all trip data, emulating legacy behaviour."""
    # Clear transactional tables
    cur.execute("DELETE FROM expenses")
    cur.execute("DELETE FROM budgets")
    cur.execute("DELETE FROM forex_cards")
    cur.execute("DELETE FROM exchange_rates")

    # Reset trips table
    cur.execute("DELETE FROM trips")
    cur.execute(
        f"""
        INSERT INTO trips (name, status, created_at, updated_at)
        VALUES ('Default Trip', 'active', ({UTC_NOW_SQL}), ({UTC_NOW_SQL}))
        """
    )
    default_trip_id = int(cur.lastrowid)

    # Handle metadata
    cur.execute("SELECT key,value FROM metadata")
    rows = cur.fetchall()
    keep = []
    if preserve_settings:
        keep = [(r["key"], r["value"]) for r in rows if _should_preserve(r["key"])]
    cur.execute("DELETE FROM metadata")
    for k, v in keep:
        cur.execute(
            f"""
            INSERT INTO metadata(key,value)
            VALUES(?,?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value,
                updated_at=({UTC_NOW_SQL})
            """,
            (k, v),
        )
    cur.execute(
        f"""
        INSERT INTO metadata(key,value)
        VALUES('active_trip_id', ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value,
            updated_at=({UTC_NOW_SQL})
        """,
        (str(default_trip_id),),
    )


__all__ = ["reset_trip_data"]
