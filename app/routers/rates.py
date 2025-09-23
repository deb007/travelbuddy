from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Dict

from app.core.config import get_settings
from app.services.rates.cache_service import (
    get_central_rate_cache_service,
    CentralRateCacheService,
)

"""Rates router (T07.04) providing manual override endpoints.

Endpoints (guarded by settings.enable_rate_override):
    - GET /rates/overrides        -> list active overrides
    - POST /rates/overrides       -> set override {currency, rate, ttl_seconds}
    - DELETE /rates/overrides/{currency} -> clear override

MVP Scope: in-memory only; process restart clears overrides. Suitable for
short-lived local usage and manual fallback when external API is down.
"""

router = APIRouter(prefix="/rates", tags=["rates"])


def get_cache_service() -> CentralRateCacheService:
    return get_central_rate_cache_service()


def require_override_enabled():
    settings = get_settings()
    if not settings.enable_rate_override:
        raise HTTPException(status_code=403, detail="rate override feature disabled")
    return True


class OverrideSetPayload(BaseModel):
    currency: str = Field(..., description="Quote currency (e.g. SGD, MYR)")
    rate: float = Field(..., gt=0, description="INR per 1 unit of currency")
    ttl_seconds: int = Field(
        900,
        gt=0,
        le=86400,
        description="Override TTL seconds (default 900 = 15m, max 24h)",
    )


@router.get("/overrides", summary="List active manual rate overrides")
async def list_overrides(
    _: bool = Depends(require_override_enabled),
    svc: CentralRateCacheService = Depends(get_cache_service),
) -> Dict[str, Dict[str, str | float]]:
    return svc.list_overrides()


@router.post("/overrides", summary="Set a manual rate override")
async def set_override(
    payload: OverrideSetPayload,
    _: bool = Depends(require_override_enabled),
    svc: CentralRateCacheService = Depends(get_cache_service),
):
    try:
        svc.set_override(payload.currency, payload.rate, payload.ttl_seconds)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {
        "status": "ok",
        "override": svc.list_overrides().get(payload.currency.upper()),
    }


@router.delete("/overrides/{currency}", summary="Clear a manual rate override")
async def clear_override(
    currency: str,
    _: bool = Depends(require_override_enabled),
    svc: CentralRateCacheService = Depends(get_cache_service),
):
    removed = svc.clear_override(currency)
    if not removed:
        raise HTTPException(status_code=404, detail="override not found")
    return {"status": "deleted", "currency": currency.upper()}
