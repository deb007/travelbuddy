from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from app.core.config import get_settings
from app.db.dal import Database
from app.services.forex_utils import card_status
from app.services.settings import get_thresholds
from app.services.trip_context import get_active_trip_id, clear_trip_context

router = APIRouter(prefix="/forex-cards", tags=["forex"])


def get_db() -> Database:
    settings = get_settings()
    return Database(settings.db_path)


class ForexLoadIn(BaseModel):
    loaded_amount: float = Field(
        ..., gt=0, description="Total loaded amount (replacement value)"
    )


class ForexCardOut(BaseModel):
    currency: str
    loaded_amount: float
    spent_amount: float
    remaining: float
    percent_remaining: float
    low_balance: bool
    low_threshold_pct: int

    @classmethod
    def from_row(cls, row: dict, forex_low_pct: int) -> "ForexCardOut":
        enriched = card_status(row, forex_low_pct)
        return cls(**enriched)


@router.put(
    "/{currency}",
    response_model=ForexCardOut,
    summary="Set / replace loaded amount for a forex card",
)
async def set_loaded_amount(
    currency: str,
    payload: ForexLoadIn,
    trip_id: Optional[int] = Query(
        None, description="Trip identifier (defaults to active trip)"
    ),
    db: Database = Depends(get_db),
):
    clear_trip_context()
    currency = currency.upper()
    resolved_trip = trip_id if trip_id is not None else get_active_trip_id(db)

    # Validate against trip-specific forex currencies
    trip_forex_currencies = db.get_trip_forex_currencies(trip_id=resolved_trip)
    if currency not in trip_forex_currencies:
        raise HTTPException(
            status_code=400,
            detail=f"Currency {currency} is not a forex currency for this trip. Valid forex currencies: {', '.join(trip_forex_currencies) if trip_forex_currencies else 'none'}",
        )

    try:
        db.set_forex_card_loaded(currency, payload.loaded_amount, trip_id=resolved_trip)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    row = db.get_forex_card(currency, trip_id=resolved_trip)
    if not row:
        raise HTTPException(status_code=500, detail="forex card not found after upsert")
    thresholds = get_thresholds(db)
    return ForexCardOut.from_row(row, thresholds.forex_low)


@router.get("/", response_model=list[ForexCardOut], summary="List forex cards")
async def list_cards(
    trip_id: Optional[int] = Query(
        None, description="Trip identifier (defaults to active trip)"
    ),
    db: Database = Depends(get_db),
):
    clear_trip_context()
    resolved_trip = trip_id if trip_id is not None else get_active_trip_id(db)
    rows = db.list_forex_cards(trip_id=resolved_trip)
    thresholds = get_thresholds(db)
    return [ForexCardOut.from_row(r, thresholds.forex_low) for r in rows]
