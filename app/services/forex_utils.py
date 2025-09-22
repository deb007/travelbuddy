from __future__ import annotations

"""Utility helpers for Forex card status (T06.04).

Keeps logic centralized so routers / future alert aggregation can reuse.
MVP threshold: low balance when remaining / loaded_amount < 0.20 (strictly below 20%).
If loaded_amount is 0, low balance is False (card effectively unused yet).
"""
from typing import Dict, Any
from app.models.forex import ForexCard

LOW_BALANCE_THRESHOLD = 0.20


def card_status(card_row: Dict[str, Any]) -> Dict[str, Any]:
    """Return enriched status for a forex card row.

    Input row keys: currency, loaded_amount, spent_amount (as from DAL).
    Output adds: remaining, percent_remaining, low_balance.
    """
    card = ForexCard(
        currency=card_row["currency"],
        loaded_amount=card_row["loaded_amount"],
        spent_amount=card_row["spent_amount"],
    )
    remaining = card.remaining
    loaded = card.loaded_amount
    if loaded <= 0:
        percent_remaining = 0.0
        low_balance = False
    else:
        percent_remaining = round(remaining / loaded * 100, 2)
        low_balance = (remaining / loaded) < LOW_BALANCE_THRESHOLD
    return {
        "currency": card.currency,
        "loaded_amount": loaded,
        "spent_amount": card.spent_amount,
        "remaining": remaining,
        "percent_remaining": percent_remaining,
        "low_balance": low_balance,
    }


def list_status(rows: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    return [card_status(r) for r in rows]
