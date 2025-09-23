from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.services.money import round2

"""INR equivalent conversion utility (T07.05).

Centralizes logic for computing INR equivalent amounts given an amount & currency.
Responsibilities:
    - Fetch rate via injected rate service (supports overrides & cache).
    - Apply rounding rules (round2) only once in a single place.
    - Return a simple immutable result object for clarity/testing.

MVP Scope: Only handles base INR & supported foreign currencies; defaults to
rate=1.0 for INR.
"""


class SupportsRateLookup(Protocol):
    def get_rate(self, currency: str) -> float: ...


@dataclass(frozen=True)
class ConversionResult:
    original_amount: float
    currency: str
    rate: float
    inr_equivalent: float


def compute_inr_equivalent(
    amount: float, currency: str, rate_service: SupportsRateLookup
) -> ConversionResult:
    currency = currency.upper()
    if currency == "INR":
        rate = 1.0
        inr_equiv = round2(amount)
    else:
        rate = rate_service.get_rate(currency)
        inr_equiv = round2(amount * rate)
    return ConversionResult(
        original_amount=amount,
        currency=currency,
        rate=rate,
        inr_equivalent=inr_equiv,
    )
