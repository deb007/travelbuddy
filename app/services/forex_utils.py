from __future__ import annotations

"""Utility helpers for Forex card status (T06.04).

Keeps logic centralized so routers / future alert aggregation can reuse.
MVP threshold: low balance when remaining / loaded_amount < 0.20 (strictly below 20%).
If loaded_amount is 0, low balance is False (card effectively unused yet).
"""
from typing import Dict, Any
from app.models.forex import ForexCard

# Retain constant for backward compatibility; dynamic threshold now retrieved
# from settings (forex_low percentage). This constant is only used as a
# fallback if settings retrieval fails unexpectedly.
LOW_BALANCE_THRESHOLD = 0.20


def card_status(card_row: Dict[str, Any], forex_low_pct: int) -> Dict[str, Any]:
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
        threshold_fraction = (
            (forex_low_pct / 100.0) if forex_low_pct else LOW_BALANCE_THRESHOLD
        )
        low_balance = (remaining / loaded) < threshold_fraction
    return {
        "currency": card.currency,
        "loaded_amount": loaded,
        "spent_amount": card.spent_amount,
        "remaining": remaining,
        "percent_remaining": percent_remaining,
        "low_balance": low_balance,
        "low_threshold_pct": forex_low_pct,
    }


def list_status(
    rows: list[Dict[str, Any]], forex_low_pct: int | None = None
) -> list[Dict[str, Any]]:
    # If caller did not pass explicit threshold, pull from settings via a DB context.
    # To avoid changing call sites drastically (they currently pass rows only), we
    # attempt to infer the DB threshold once. Since rows come from a DB query, we
    # require caller to provide threshold or separately fetch in orchestration
    # code. Here we lazily fetch using any available DB if threshold not supplied.
    if forex_low_pct is None:
        # Fall back to legacy constant (20%). Higher layers (alerts, UI) should
        # fetch dynamic threshold via settings service and pass explicitly.
        forex_low_pct = int(LOW_BALANCE_THRESHOLD * 100)
    return [card_status(r, forex_low_pct) for r in rows]
