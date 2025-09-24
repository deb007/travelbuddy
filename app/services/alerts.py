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
from typing import List, Dict, Any

from app.db.dal import Database
from app.services.budget_utils import list_budget_statuses
from app.services.forex_utils import list_status as list_forex_status


def collect_alerts(db: Database) -> List[Dict[str, Any]]:
    alerts: List[Dict[str, Any]] = []

    # Budget alerts
    for b in list_budget_statuses(db):
        if b["ninety"]:
            alerts.append(
                {
                    "type": "budget",
                    "currency": b["currency"],
                    "level": "danger",
                    "message": f"{b['currency']} budget at {b['percent_used']}% (>=90%)",
                }
            )
        elif b["eighty"]:
            alerts.append(
                {
                    "type": "budget",
                    "currency": b["currency"],
                    "level": "warn",
                    "message": f"{b['currency']} budget at {b['percent_used']}% (>=80%)",
                }
            )

    # Forex alerts
    for c in list_forex_status(db.list_forex_cards()):
        if c["low_balance"]:
            alerts.append(
                {
                    "type": "forex",
                    "currency": c["currency"],
                    "level": "warn",
                    "message": f"{c['currency']} forex remaining {c['percent_remaining']}% (<20%)",
                }
            )

    return alerts


__all__ = ["collect_alerts"]
