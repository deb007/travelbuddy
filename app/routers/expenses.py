from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime

from app.core.config import get_settings
from app.db.dal import Database
from app.models.expense import ExpenseIn, ExpenseOut
from app.services.expense_validation import validate_expense_domain
from app.services.rate_service import RateService

router = APIRouter(prefix="/expenses", tags=["expenses"])

# Dependencies -----------------------------------------------------


def get_db() -> Database:
    settings = get_settings()
    return Database(settings.db_path)


def get_rate_service() -> RateService:
    return RateService()


# Request / Response Models (thin wrappers if needed) --------------
class ExpenseCreateResponse(BaseModel):
    expense: ExpenseOut


# Helpers ----------------------------------------------------------


def _row_to_expense_out(row: dict) -> ExpenseOut:
    return ExpenseOut(
        id=row["id"],
        amount=row["amount"],
        currency=row["currency"],
        category=row["category"],
        description=row.get("description"),
        date=datetime.strptime(row["date"], "%Y-%m-%d").date(),
        payment_method=row["payment_method"],
        inr_equivalent=row["inr_equivalent"],
        exchange_rate=row["exchange_rate"],
        created_at=datetime.fromisoformat(row["created_at"].replace("Z", "")),
        updated_at=datetime.fromisoformat(row["updated_at"].replace("Z", "")),
    )


# Routes -----------------------------------------------------------
@router.post(
    "/", response_model=ExpenseOut, status_code=201, summary="Create an expense"
)
async def create_expense(
    payload: ExpenseIn,
    db: Database = Depends(get_db),
    rate_service: RateService = Depends(get_rate_service),
):
    # 1. Domain validation hook (trip date boundaries etc. later)
    validate_expense_domain(payload)

    # 2. Compute INR equivalent (stub rate service)
    if payload.currency == "INR":
        inr_equivalent = payload.amount
        exchange_rate = 1.0
    else:
        exchange_rate = rate_service.get_rate(payload.currency)
        inr_equivalent = rate_service.compute_inr(payload.amount, payload.currency)

    # 3. Persist (atomic budget spent increment via dedicated DAL method)
    try:
        expense_id = db.insert_expense_with_budget(
            expense=payload,
            inr_equivalent=inr_equivalent,
            exchange_rate=exchange_rate,
        )
    except Exception as e:  # pragma: no cover - generic safety
        raise HTTPException(status_code=500, detail="failed to persist expense") from e

    # 4. Fetch row to build response
    row = db.get_expense(expense_id)
    if not row:
        raise HTTPException(status_code=500, detail="expense not found after insert")

    return _row_to_expense_out(row)
