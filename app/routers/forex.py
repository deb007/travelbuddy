from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.core.config import get_settings
from app.db.dal import Database
from app.models.constants import FOREX_CURRENCIES
from app.services.forex_utils import card_status

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

    @classmethod
    def from_row(cls, row: dict) -> "ForexCardOut":
        enriched = card_status(row)
        return cls(**enriched)


@router.put(
    "/{currency}",
    response_model=ForexCardOut,
    summary="Set / replace loaded amount for a forex card",
)
async def set_loaded_amount(
    currency: str, payload: ForexLoadIn, db: Database = Depends(get_db)
):
    currency = currency.upper()
    if currency not in FOREX_CURRENCIES:
        raise HTTPException(status_code=400, detail="unsupported forex currency")
    try:
        db.set_forex_card_loaded(currency, payload.loaded_amount)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    row = db.get_forex_card(currency)
    if not row:
        raise HTTPException(status_code=500, detail="forex card not found after upsert")
    return ForexCardOut.from_row(row)


@router.get("/", response_model=list[ForexCardOut], summary="List forex cards")
async def list_cards(db: Database = Depends(get_db)):
    rows = db.list_forex_cards()
    return [ForexCardOut.from_row(r) for r in rows]
