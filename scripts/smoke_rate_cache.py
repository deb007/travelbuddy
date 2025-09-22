"""Smoke script for central rate cache (T07.03).

Demonstrates:
 1. First access triggers underlying provider fetch.
 2. Subsequent access within TTL uses cached rates (no visible change, but we show timestamps).
 3. Manual TTL shortening simulation: we directly mutate internal _cache timestamps to force refresh.

NOTE: This is a lightweight diagnostic and not a formal test.
"""

from datetime import datetime, timedelta
from pprint import pprint

from app.services.rates.cache_service import get_central_rate_cache_service


def run():
    svc = get_central_rate_cache_service()
    out = {"initial": {}, "second": {}, "forced_refresh": {}}

    # Initial fetch
    for c in ("SGD", "MYR"):
        rate = svc.get_rate(c)
        out["initial"][c] = {
            "rate": rate,
            "fetched_at": svc._cache[c].fetched_at.isoformat(),  # type: ignore[attr-defined]
        }

    # Second fetch (should reuse timestamps)
    for c in ("SGD", "MYR"):
        rate = svc.get_rate(c)
        out["second"][c] = {
            "rate": rate,
            "fetched_at": svc._cache[c].fetched_at.isoformat(),  # type: ignore[attr-defined]
        }

    # Force refresh by backdating fetched_at beyond TTL
    for entry in svc._cache.values():  # type: ignore[attr-defined]
        entry.fetched_at = datetime.utcnow() - timedelta(
            seconds=svc._ttl.total_seconds() + 5
        )  # type: ignore[attr-defined]

    for c in ("SGD", "MYR"):
        rate = svc.get_rate(c)
        out["forced_refresh"][c] = {
            "rate": rate,
            "fetched_at": svc._cache[c].fetched_at.isoformat(),  # type: ignore[attr-defined]
        }

    pprint(out)


if __name__ == "__main__":
    run()
