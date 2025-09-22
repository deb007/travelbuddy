from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Dict, Iterable

from app.core.config import get_settings
from app.services.money import round2
from .providers import make_rate_provider, RateServiceFacade

"""Central rate cache service (T07.03).

Purpose:
    Provide a single place to cache INR per unit rates for supported quote currencies
    (currently SGD, MYR) for a configurable TTL (settings.rates_cache_ttl_seconds).

Design:
    - Wraps an underlying RateProvider (selected via settings.exchange_rate_provider).
    - Maintains an in-memory dict of last fetched rates + timestamp.
    - Exposes get_rate() and compute_inr() similar to RateServiceFacade so routers
      can depend on this service going forward.
    - If TTL expired -> refresh by asking underlying provider for each needed currency.
    - Missing currency falls back to 1.0 (INR) to keep MVP resilient.

Why separate from provider-level caching?
    ExternalHTTPRateProvider already has an internal short/medium cache. This layer
    establishes a uniform, higher level cache whose TTL is controlled globally, so
    future features (manual override T07.04) can inject / overwrite values centrally
    without modifying each provider implementation.

Future (T07.04):
    Manual override will set entries here with an override_expiry; logic can be
    extended to check override store before delegating.
"""

SUPPORTED_QUOTES: Iterable[str] = ("SGD", "MYR")  # extend as needed


@dataclass
class _CacheEntry:
    rate: float
    fetched_at: datetime


class CentralRateCacheService:
    """Cached rate service with TTL-bound entries.

    Public API mirrors RateServiceFacade to avoid broad refactors elsewhere.
    """

    def __init__(self):
        self._settings = get_settings()
        provider = make_rate_provider(self._settings.exchange_rate_provider)
        # Reuse existing facade for compute logic (rounding rules).
        self._underlying = RateServiceFacade(provider)
        self._ttl = timedelta(seconds=self._settings.rates_cache_ttl_seconds)
        self._cache: Dict[str, _CacheEntry] = {}

    # Internal --------------------------------------------------
    def _is_entry_valid(self, entry: _CacheEntry) -> bool:
        return datetime.utcnow() - entry.fetched_at < self._ttl

    def _refresh_currency(self, currency: str) -> float:
        rate = self._underlying.get_rate(currency)
        self._cache[currency] = _CacheEntry(rate=rate, fetched_at=datetime.utcnow())
        return rate

    def _get_cached_or_refresh(self, currency: str) -> float:
        currency = currency.upper()
        entry = self._cache.get(currency)
        if entry and self._is_entry_valid(entry):
            return entry.rate
        # Only refresh supported quotes; anything else (e.g., INR) trivial
        if currency in SUPPORTED_QUOTES:
            return self._refresh_currency(currency)
        # For base / unsupported pass-through (INR or others default 1.0)
        return 1.0

    # Public API -----------------------------------------------
    def get_rate(self, currency: str) -> float:
        if currency.upper() == "INR":
            return 1.0
        return self._get_cached_or_refresh(currency)

    def compute_inr(self, amount: float, currency: str) -> float:
        rate = self.get_rate(currency)
        return round2(amount * rate)


# Singleton dependency helper used by FastAPI DI
@lru_cache
def get_central_rate_cache_service() -> CentralRateCacheService:
    return CentralRateCacheService()
