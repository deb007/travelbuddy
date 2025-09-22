"""Budget utility helpers (T03.04 Remaining calc util).

Provides lightweight transformation functions to augment raw budget rows with
remaining amounts, percent used, and threshold flags (80%, 90%). Designed to
stay framework-agnostic so both API routes and future template rendering can
reuse the same logic.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional

from app.db.dal import Database

THRESHOLDS = (80, 90)


def budget_status(row: Dict[str, Any]) -> Dict[str, Any]:
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
        "eighty": percent_used >= THRESHOLDS[0] if max_amount > 0 else False,
        "ninety": percent_used >= THRESHOLDS[1] if max_amount > 0 else False,
    }
    return status


def get_budget_status(db: Database, currency: str) -> Optional[Dict[str, Any]]:
    row = db.get_budget(currency)
    return budget_status(row) if row else None


def list_budget_statuses(db: Database) -> List[Dict[str, Any]]:
    return [budget_status(r) for r in db.list_budgets()]
