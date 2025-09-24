"""Budget utility helpers (T03.04 Remaining calc util).

Provides lightweight transformation functions to augment raw budget rows with
remaining amounts, percent used, and threshold flags (80%, 90%). Designed to
stay framework-agnostic so both API routes and future template rendering can
reuse the same logic.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional

from app.db.dal import Database
from app.services.settings import get_thresholds

# Deprecated constant kept for backward compatibility; dynamic values now
# retrieved per-call from settings metadata. If settings unavailable, defaults
# (80,90) from settings service will be returned.
THRESHOLDS = (80, 90)


def budget_status(
    row: Dict[str, Any], warn_pct: int, danger_pct: int
) -> Dict[str, Any]:
    max_amount = row.get("max_amount", 0) or 0
    spent = row.get("spent_amount", 0) or 0
    remaining = max(max_amount - spent, 0)
    percent_used = 0.0
    if max_amount > 0:
        percent_used = round((spent / max_amount) * 100, 2)
    status = {
        "currency": row.get("currency"),
        "max_amount": float(max_amount),
        "spent_amount": float(spent),
        "remaining": round(float(remaining), 2),
        "percent_used": percent_used,
        # Preserve legacy keys 'eighty' and 'ninety' for existing templates / callers.
        "eighty": percent_used >= warn_pct if max_amount > 0 else False,
        "ninety": percent_used >= danger_pct if max_amount > 0 else False,
        # New generic keys aligned with settings naming.
        "warn": percent_used >= warn_pct if max_amount > 0 else False,
        "danger": percent_used >= danger_pct if max_amount > 0 else False,
        "warn_threshold": warn_pct,
        "danger_threshold": danger_pct,
    }
    return status


def get_budget_status(db: Database, currency: str) -> Optional[Dict[str, Any]]:
    row = db.get_budget(currency)
    if not row:
        return None
    th = get_thresholds(db)
    return budget_status(row, th.budget_warn, th.budget_danger)


def list_budget_statuses(db: Database) -> List[Dict[str, Any]]:
    th = get_thresholds(db)
    return [
        budget_status(r, th.budget_warn, th.budget_danger) for r in db.list_budgets()
    ]
