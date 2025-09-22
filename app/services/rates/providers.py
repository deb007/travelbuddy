from __future__ import annotations

"""Concrete rate providers and factory (T07.01).

'ExternalPlaceholderRateProvider' stands in for a future HTTP-based provider; it simply
returns slightly different constants so we can demonstrate a switch.
"""
from typing import Dict, Optional
from datetime import datetime, timedelta
from .base import RateProvider
from app.services.money import round2
from app.services.http_client import get_json, HttpError

_STATIC_RATES: Dict[str, float] = {
    "INR": 1.0,
    "SGD": 62.0,
    "MYR": 18.0,
}

# Slightly shifted values to show provider effect
_EXTERNAL_PLACEHOLDER_RATES: Dict[str, float] = {
    "INR": 1.0,
    "SGD": 61.5,
    "MYR": 18.2,
}


class StaticRateProvider(RateProvider):
    def get_rate(self, quote_currency: str) -> float:  # type: ignore[override]
        return _STATIC_RATES.get(quote_currency.upper(), 1.0)


class ExternalPlaceholderRateProvider(RateProvider):
    def get_rate(self, quote_currency: str) -> float:  # type: ignore[override]
        return _EXTERNAL_PLACEHOLDER_RATES.get(quote_currency.upper(), 1.0)


_PROVIDER_REGISTRY = {
    "static": StaticRateProvider,
    "external-placeholder": ExternalPlaceholderRateProvider,
    # Added in T07.02
    "external-http": None,  # placeholder; populated after class definition
}


def make_rate_provider(kind: str) -> RateProvider:
    cls = _PROVIDER_REGISTRY.get(kind)
    if not cls:
        raise ValueError(f"Unknown rate provider kind '{kind}'")
    return cls()


class RateServiceFacade:
    """Thin facade maintaining old RateService compute_inr API for routers.

    This allows incremental migration: routers depend on facade, which delegates
    to the configured provider.
    """

    def __init__(self, provider: RateProvider):
        self._provider = provider

    def get_rate(self, currency: str) -> float:
        return self._provider.get_rate(currency)

    def compute_inr(self, amount: float, currency: str) -> float:
        rate = self.get_rate(currency)
        return round2(amount * rate)


# (T07.02) External HTTP provider leveraging exchangerate.host (free, no key required)
# We fetch latest base=INR and keep rates for SGD/MYR. Minimal in-memory cache.
class ExternalHTTPRateProvider(RateProvider):
    _CACHE_TTL = timedelta(minutes=30)

    def __init__(self):
        self._cache_expires: Optional[datetime] = None
        self._rates: Dict[str, float] = {}

    def _refresh_if_needed(self) -> None:
        now = datetime.utcnow()
        if self._cache_expires and now < self._cache_expires:
            return
        url = "https://api.exchangerate.host/latest?base=INR&symbols=SGD,MYR,INR"
        try:
            data = get_json(url, timeout=5.0, retries=2)
            rates = data.get("rates") or {}
            # The API returns quote in target currency per base unit; we need INR per unit of quote.
            # Since base=INR, rates[SGD] = SGD per INR. We invert to get INR per 1 SGD.
            new_rates: Dict[str, float] = {"INR": 1.0}
            for qc in ("SGD", "MYR"):
                v = rates.get(qc)
                if v and v > 0:
                    new_rates[qc] = round2(1 / v)
            # Fallback to static placeholders if missing
            for qc, val in _STATIC_RATES.items():
                new_rates.setdefault(qc, val)
            self._rates = new_rates
            self._cache_expires = now + self._CACHE_TTL
        except HttpError:
            # On failure we degrade gracefully to static
            self._rates = dict(_STATIC_RATES)
            self._cache_expires = now + timedelta(minutes=5)

    def get_rate(self, quote_currency: str) -> float:  # type: ignore[override]
        self._refresh_if_needed()
        return self._rates.get(quote_currency.upper(), 1.0)


# Register external-http after class definition
_PROVIDER_REGISTRY["external-http"] = ExternalHTTPRateProvider
