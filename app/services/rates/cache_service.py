from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Dict, Iterable, TYPE_CHECKING

from app.core.config import get_settings
from app.services.app_settings import (
    get_effective_rate_provider,
    get_rates_cache_ttl,
)

if TYPE_CHECKING:  # pragma: no cover
    from app.db.dal import Database
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


@dataclass
class _OverrideEntry:
    rate: float
    expires_at: datetime


class CentralRateCacheService:
    """Cached rate service with TTL-bound entries.

    Public API mirrors RateServiceFacade to avoid broad refactors elsewhere.
    """

    def __init__(self, db: "Database" | None = None):  # db optional for DI override
        self._settings = get_settings()
        # If DB provided, allow dynamic override of provider & TTL via metadata
        if db is not None:
            provider_name = get_effective_rate_provider(db)
            ttl_seconds = get_rates_cache_ttl(db)
        else:
            provider_name = self._settings.exchange_rate_provider
            ttl_seconds = self._settings.rates_cache_ttl_seconds
        provider = make_rate_provider(provider_name)
        # Reuse existing facade for compute logic (rounding rules).
        self._underlying = RateServiceFacade(provider)
        self._ttl = timedelta(seconds=ttl_seconds)
        self._cache: Dict[str, _CacheEntry] = {}
        # Manual overrides (T07.04). Keyed by currency upper.
        self._overrides: Dict[str, _OverrideEntry] = {}

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
    def _purge_expired_overrides(self) -> None:
        now = datetime.utcnow()
        expired = [k for k, v in self._overrides.items() if v.expires_at <= now]
        for k in expired:
            self._overrides.pop(k, None)

    # Manual override API (T07.04) -----------------------------
    def set_override(self, currency: str, rate: float, ttl_seconds: int) -> None:
        currency = currency.upper()
        if rate <= 0:
            raise ValueError("override rate must be positive")
        if ttl_seconds <= 0:
            raise ValueError("override ttl must be positive seconds")
        self._overrides[currency] = _OverrideEntry(
            rate=rate, expires_at=datetime.utcnow() + timedelta(seconds=ttl_seconds)
        )

    def clear_override(self, currency: str) -> bool:
        currency = currency.upper()
        return self._overrides.pop(currency, None) is not None

    def list_overrides(self) -> Dict[str, Dict[str, str | float]]:
        self._purge_expired_overrides()
        return {
            c: {"rate": v.rate, "expires_at": v.expires_at.isoformat()}
            for c, v in self._overrides.items()
        }

    def get_rate(self, currency: str) -> float:
        if currency.upper() == "INR":
            return 1.0
        self._purge_expired_overrides()
        ov = self._overrides.get(currency.upper())
        if ov:
            return ov.rate
        return self._get_cached_or_refresh(currency)

    def compute_inr(self, amount: float, currency: str) -> float:
        rate = self.get_rate(currency)
        return round2(amount * rate)


# Singleton dependency helper used by FastAPI DI
@lru_cache
def get_central_rate_cache_service() -> CentralRateCacheService:  # legacy no-DB path
    return CentralRateCacheService()


def build_dynamic_rate_cache_service(db: "Database") -> CentralRateCacheService:
    """Factory that bypasses lru_cache so dynamic metadata changes apply immediately.

    Use this in contexts (settings update, admin panel) where immediate reflection
    of provider/TTL changes is desired without process restart. Regular routes can
    continue using the cached singleton for performance; they will reflect changes
    after application restart or if code is adjusted later to refresh.
    """
    return CentralRateCacheService(db)
