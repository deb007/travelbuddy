"""Alert aggregation service (T10.03).

Consolidates logic for budget threshold alerts (>=80%, >=90%) and forex low
balance (<20%). Provides a single function `collect_alerts` returning a list of
alert dicts with consistent shape so UI & future APIs can consume uniformly.

Alert schema (dict):
  type: 'budget' | 'forex'
  currency: str
  level: 'warn' | 'danger'
  message: human readable string

The thresholds themselves remain defined in their respective domain utility
modules to avoid duplication. This module only orchestrates and formats.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional

from app.db.dal import Database
from app.services.budget_utils import list_budget_statuses
from app.services.forex_utils import list_status as list_forex_status
from app.services.settings import get_thresholds


def collect_alerts(db: Database, trip_id: Optional[int] = None) -> List[Dict[str, Any]]:
    alerts: List[Dict[str, Any]] = []

    th = get_thresholds(db)

    # Budget alerts (dynamic thresholds)
    for b in list_budget_statuses(db, trip_id=trip_id):
        if b["danger"]:
            alerts.append(
                {
                    "type": "budget",
                    "currency": b["currency"],
                    "level": "danger",
                    "message": f"{b['currency']} budget at {b['percent_used']}% (>={th.budget_danger}%)",
                }
            )
        elif b["warn"]:
            alerts.append(
                {
                    "type": "budget",
                    "currency": b["currency"],
                    "level": "warn",
                    "message": f"{b['currency']} budget at {b['percent_used']}% (>={th.budget_warn}%)",
                }
            )

    # Forex alerts (dynamic threshold)
    forex_rows = db.list_forex_cards(trip_id=trip_id)
    for c in list_forex_status(forex_rows, forex_low_pct=th.forex_low):
        if c["low_balance"]:
            alerts.append(
                {
                    "type": "forex",
                    "currency": c["currency"],
                    "level": "warn",
                    "message": f"{c['currency']} forex remaining {c['percent_remaining']}% (<{th.forex_low}%)",
                }
            )

    return alerts


__all__ = ["collect_alerts"]
