"""Exchange rate service stub for MVP (T04.02).

Full implementation will arrive in T07.* tasks. For now we provide a simple
in-memory stub with hardcoded fallback rates and a method to compute the INR
equivalent for a given original amount + currency.

Design:
- Base currency: INR
- Supported quote currencies: SGD, MYR (others default to 1.0)
- `get_rate(quote_currency)` returns a float (INR per 1 unit of quote)
- `compute_inr(amount, currency)` returns rounded INR amount (2 decimals)

Later (T07.03): this module will evolve to fetch & cache real rates, possibly
exposing async methods. The router uses it via a lightweight dependency so
future replacement is trivial.
"""

from __future__ import annotations
from typing import Dict
from .money import round2

_DEFAULT_RATES: Dict[str, float] = {
    "INR": 1.0,  # base
    "SGD": 62.0,  # placeholder
    "MYR": 18.0,  # placeholder
}


class RateService:
    def __init__(self):
        # In future we could inject settings/cache
        pass

    def get_rate(self, currency: str) -> float:
        return _DEFAULT_RATES.get(currency.upper(), 1.0)

    def compute_inr(self, amount: float, currency: str) -> float:
        rate = self.get_rate(currency)
        return round2(amount * rate)
