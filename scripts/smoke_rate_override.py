"""Smoke script for manual rate override (T07.04).

Sequence:
 1. Fetch baseline rates via central cache.
 2. Set override for SGD with short TTL.
 3. Fetch rate again (should use override).
 4. Clear override and fetch rate (should revert to cached/provider rate).
"""

from pprint import pprint
from time import sleep

from app.services.rates.cache_service import get_central_rate_cache_service


def run():
    svc = get_central_rate_cache_service()
    output = {}

    # Baseline
    base_rate = svc.get_rate("SGD")
    output["baseline"] = base_rate

    # Set override (TTL 30s) with obviously different value
    svc.set_override("SGD", rate=99.99, ttl_seconds=30)
    override_rate = svc.get_rate("SGD")
    output["override_active"] = override_rate
    output["overrides_list_after_set"] = svc.list_overrides()

    # Clear override
    svc.clear_override("SGD")
    cleared_rate = svc.get_rate("SGD")
    output["after_clear"] = cleared_rate

    # Re-set with 1s TTL to show expiry path
    svc.set_override("SGD", rate=88.88, ttl_seconds=1)
    short_active = svc.get_rate("SGD")
    sleep(1.2)
    expired_rate = svc.get_rate("SGD")
    output["short_override_active"] = short_active
    output["after_expiry"] = expired_rate

    pprint(output)


if __name__ == "__main__":
    run()
