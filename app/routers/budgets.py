from typing import Optional

from fastapi import APIRouter, Depends, Path, HTTPException, Query
from pydantic import BaseModel, Field
from app.core.config import get_settings
from app.models.budget import Budget
from app.models.constants import CURRENCIES
from app.db.dal import Database
from app.services.trip_context import get_active_trip_id, clear_trip_context

router = APIRouter(prefix="/budgets", tags=["budgets"])


def get_db() -> Database:
    settings = get_settings()
    return Database(settings.db_path)


class BudgetUpdateIn(BaseModel):
    max_amount: float = Field(
        ..., gt=0, description="New maximum budget amount (must be > 0)"
    )


@router.put(
    "/{currency}", response_model=Budget, summary="Create or update a budget max amount"
)
async def upsert_budget(
    currency: str = Path(
        ..., description="Currency code", examples=["INR", "SGD", "MYR"]
    ),
    payload: BudgetUpdateIn = None,
    trip_id: Optional[int] = Query(
        None, description="Trip identifier (defaults to active trip)"
    ),
    db: Database = Depends(get_db),
):
    clear_trip_context()
    currency = currency.upper()
    if currency not in CURRENCIES:
        raise HTTPException(status_code=400, detail="unsupported currency")
    resolved_trip = trip_id if trip_id is not None else get_active_trip_id(db)
    db.set_budget_max(currency, payload.max_amount, trip_id=resolved_trip)
    row = db.get_budget(currency, trip_id=resolved_trip)
    if not row:
        raise HTTPException(status_code=500, detail="failed to persist budget")
    return Budget(**row)
