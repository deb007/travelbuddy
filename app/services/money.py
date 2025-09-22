"""Money / rounding helpers.

Centralized so analytics, rate service, and future endpoints use identical
rounding semantics.
"""

from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP


def round2(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
