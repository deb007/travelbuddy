from datetime import date
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import HTTPException
from typing import List
from pydantic import ValidationError

from app.core.config import get_settings
from app.db.dal import Database
from app.services.timeline import get_trip_dates, resolve_phase
from app.services.budget_utils import list_budget_statuses
from app.services.analytics_utils import (
    compute_average_daily_spend,
    compute_remaining_daily_budget,
    compute_currency_breakdown,
    compute_category_breakdown,
)
from app.services.rates.cache_service import get_central_rate_cache_service
from app.models.constants import CURRENCIES, CATEGORIES, PAYMENT_METHODS
from app.models.expense import ExpenseIn
from app.services.expense_validation import validate_expense_domain
from app.services.rates.conversion import compute_inr_equivalent

router = APIRouter(tags=["ui"])

templates = Jinja2Templates(directory="app/templates")


def get_db():  # lightweight for MVP; could be shared dependency
    settings = get_settings()
    return Database(settings.db_path)


def compute_phase(db: Database):
    trip_dates = get_trip_dates(db)
    if trip_dates:
        phase = resolve_phase(date.today(), trip_dates)
    else:
        phase = "trip"  # default semantics
    return phase


@router.get("/ui", response_class=HTMLResponse)
async def ui_home(request: Request, db: Database = Depends(get_db)):
    phase = compute_phase(db)
    settings = get_settings()

    # Metrics
    budgets = list_budget_statuses(db)
    avg = compute_average_daily_spend(db)
    remaining = compute_remaining_daily_budget(db)
    currency_breakdown = compute_currency_breakdown(db)
    category_breakdown = compute_category_breakdown(db)

    rate_service = get_central_rate_cache_service()
    rates = []
    for cur in ("SGD", "MYR"):
        try:
            rate = rate_service.get_rate(cur)
            rates.append({"currency": cur, "rate": rate})
        except Exception:
            rates.append({"currency": cur, "rate": "-"})

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "current_phase": phase,
            "version": settings.version,
            "budgets": budgets,
            "avg": avg,
            "remaining": remaining,
            "currency_breakdown": currency_breakdown,
            "category_breakdown": category_breakdown,
            "rates": rates,
        },
    )


@router.get("/ui/expenses/new", response_class=HTMLResponse)
async def ui_expense_form(request: Request, db: Database = Depends(get_db)):
    phase = compute_phase(db)
    settings = get_settings()
    # Initial blank form data
    form = {}
    return templates.TemplateResponse(
        "expense_form.html",
        {
            "request": request,
            "current_phase": phase,
            "version": settings.version,
            "currencies": sorted(CURRENCIES),
            "categories": sorted(CATEGORIES),
            "payment_methods": sorted(PAYMENT_METHODS),
            "errors": [],
            "form": form,
            "success": False,
        },
    )


@router.post("/ui/expenses/new", response_class=HTMLResponse)
async def ui_expense_form_submit(
    request: Request,
    amount: float = Form(...),
    currency: str = Form(...),
    category: str = Form(...),
    payment_method: str = Form(...),
    date: str = Form(...),  # ISO string
    description: str | None = Form(None),
    db: Database = Depends(get_db),
):
    phase = compute_phase(db)
    settings = get_settings()
    errors: List[str] = []
    form_state = {
        "amount": amount,
        "currency": currency,
        "category": category,
        "payment_method": payment_method,
        "date": date,
        "description": description,
    }

    # Basic normalization
    currency = currency.upper()
    category = category.strip()
    payment_method = payment_method.strip()

    # Build model & validate
    from datetime import date as date_cls

    try:
        parsed_date = date_cls.fromisoformat(date)
    except ValueError:
        errors.append("Invalid date format")
        parsed_date = None

    if parsed_date:
        try:
            expense_in = ExpenseIn(
                amount=amount,
                currency=currency,
                category=category,
                description=description if description else None,
                date=parsed_date,
                payment_method=payment_method,
            )
            # Domain level validations
            validate_expense_domain(expense_in)
        except ValidationError as ve:
            for err in ve.errors():
                loc = ".".join([str(p) for p in err.get("loc", [])])
                msg = err.get("msg", "invalid")
                errors.append(f"{loc}: {msg}")
        except HTTPException as he:  # from domain validate
            errors.append(he.detail)
        except Exception:  # pragma: no cover
            errors.append("Unexpected validation error")
    else:
        expense_in = None

    created_expense = None
    if not errors and expense_in:
        # Rate compute & persist (reuse central rate cache service)
        rate_service = get_central_rate_cache_service()
        try:
            conv = compute_inr_equivalent(
                expense_in.amount, expense_in.currency, rate_service
            )
            expense_id = db.insert_expense_with_budget(
                expense=expense_in,
                inr_equivalent=conv.inr_equivalent,
                exchange_rate=conv.rate,
            )
            row = db.get_expense(expense_id)
            if row:
                created_expense = {
                    "id": row["id"],
                    "amount": row["amount"],
                    "currency": row["currency"],
                    "category": row["category"],
                }
            else:
                errors.append("Expense persisted but not retrievable")
        except Exception:
            errors.append("Failed to save expense")

    success = created_expense is not None and not errors

    if success:
        # Clear form state after success except maybe date for faster entry
        form_state = {"date": date}

    return templates.TemplateResponse(
        "expense_form.html",
        {
            "request": request,
            "current_phase": phase,
            "version": settings.version,
            "currencies": sorted(CURRENCIES),
            "categories": sorted(CATEGORIES),
            "payment_methods": sorted(PAYMENT_METHODS),
            "errors": errors,
            "form": form_state,
            "success": success,
            "created_expense": created_expense,
        },
    )
