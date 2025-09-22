from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from datetime import datetime, date
from typing import List, Optional
from app.models.constants import CURRENCIES

from app.core.config import get_settings
from app.db.dal import Database
from app.models.expense import ExpenseIn, ExpenseOut, ExpenseUpdateIn
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


@router.get(
    "/", response_model=List[ExpenseOut], summary="List expenses with optional filters"
)
async def list_expenses_endpoint(
    start_date: Optional[date] = Query(
        None, description="Filter: start date inclusive"
    ),
    end_date: Optional[date] = Query(None, description="Filter: end date inclusive"),
    currency: Optional[str] = Query(None, description="Filter by original currency"),
    phase: Optional[str] = Query(
        None,
        description="Stub param for future phase filtering (pre-trip|trip). Currently returns 400 if provided because timeline not implemented yet.",
    ),
    db: Database = Depends(get_db),
):
    # 1. Phase handling stub
    if phase is not None:
        raise HTTPException(status_code=400, detail="phase filter not available yet")
    # 2. Date ordering validation
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=400, detail="start_date cannot be after end_date"
        )
    # 3. Currency validation
    if currency:
        currency = currency.upper()
        if currency not in CURRENCIES:
            raise HTTPException(status_code=400, detail="unsupported currency")
    # 4. Fetch
    rows = db.list_expenses(start_date=start_date, end_date=end_date, currency=currency)
    return [_row_to_expense_out(r) for r in rows]


@router.patch(
    "/{expense_id}", response_model=ExpenseOut, summary="Edit an expense (partial)"
)
async def patch_expense(
    expense_id: int,
    payload: ExpenseUpdateIn,
    db: Database = Depends(get_db),
    rate_service: RateService = Depends(get_rate_service),
):
    # 1. Fetch existing expense
    row = db.get_expense(expense_id)
    if not row:
        raise HTTPException(status_code=404, detail="expense not found")

    # 2. Currency immutability (ignore if user tries to include, model doesn't allow)
    original_amount = float(row["amount"])
    currency = row["currency"]

    # 3. Build merged object for validation using ExpenseIn semantics
    merged = ExpenseIn(
        amount=payload.amount if payload.amount is not None else original_amount,
        currency=currency,
        category=payload.category if payload.category is not None else row["category"],
        description=payload.description
        if payload.description is not None
        else row.get("description"),
        date=payload.date
        if payload.date is not None
        else datetime.strptime(row["date"], "%Y-%m-%d").date(),
        payment_method=payload.payment_method
        if payload.payment_method is not None
        else row["payment_method"],
    )
    # Domain hook
    validate_expense_domain(merged)

    # 4. Determine amount delta & recompute INR equivalent if amount changed
    new_amount = merged.amount
    budget_delta = new_amount - original_amount
    if currency == "INR":
        new_exchange_rate = 1.0
        new_inr_equivalent = new_amount
    else:
        # Recompute only if amount changed; but simplest is always recompute for currency consistency
        new_exchange_rate = rate_service.get_rate(currency)
        new_inr_equivalent = rate_service.compute_inr(new_amount, currency)

    # 5. Persist atomically
    try:
        db.update_expense_with_budget(
            expense_id=expense_id,
            new_amount=new_amount,
            new_category=merged.category,
            new_description=merged.description,
            new_date=merged.date,
            new_payment_method=merged.payment_method,
            new_inr_equivalent=new_inr_equivalent,
            new_exchange_rate=new_exchange_rate,
            budget_delta=budget_delta,
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="expense not found")
    except Exception as e:  # pragma: no cover
        raise HTTPException(status_code=500, detail="failed to update expense") from e

    # 6. Return updated record
    updated = db.get_expense(expense_id)
    if not updated:
        raise HTTPException(status_code=500, detail="expense disappeared after update")
    return _row_to_expense_out(updated)


@router.delete(
    "/{expense_id}", status_code=204, summary="Delete an expense and adjust budget"
)
async def delete_expense(
    expense_id: int,
    db: Database = Depends(get_db),
):
    try:
        db.delete_expense_with_budget(expense_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="expense not found")
    except Exception as e:  # pragma: no cover
        raise HTTPException(status_code=500, detail="failed to delete expense") from e
    return None
