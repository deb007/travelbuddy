from datetime import date
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import HTTPException
from typing import List, Optional
from pydantic import ValidationError

from app.core.config import get_settings
from app.db.dal import Database
from app.services.timeline import get_trip_dates, resolve_phase
from app.services.budget_utils import list_budget_statuses
from app.services.forex_utils import list_status as list_forex_status
from app.services.alerts import collect_alerts
from app.services.analytics_utils import (
    compute_average_daily_spend,
    compute_remaining_daily_budget,
    compute_currency_breakdown,
    compute_category_breakdown,
)
from app.services.rates.cache_service import get_central_rate_cache_service
from app.models.constants import CURRENCIES, CATEGORIES, PAYMENT_METHODS
from app.models.expense import ExpenseIn, ExpenseUpdateIn
from app.services.expense_validation import validate_expense_domain
from app.services.rates.conversion import compute_inr_equivalent
from app.services.money import round2

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

    # Alerts aggregation via centralized service (T10.03)
    alerts = collect_alerts(db)

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
            "alerts": alerts,
            "alerts_count": len(alerts),
        },
    )


@router.get("/ui/budgets", response_class=HTMLResponse)
async def ui_budgets(request: Request, db: Database = Depends(get_db)):
    """Standalone budgets page (T10.01) highlighting threshold logic.

    Reuses existing budget status utility that already exposes 80% / 90% flags.
    Provides an at-a-glance view plus simple legend without duplicating logic
    implemented in dashboard.
    """
    phase = compute_phase(db)
    settings = get_settings()
    budgets = list_budget_statuses(db)

    # Derive counts for thresholds (purely presentational)
    total = len(budgets)
    warn_list = [b for b in budgets if b["eighty"] and not b["ninety"]]
    danger_list = [b for b in budgets if b["ninety"]]

    return templates.TemplateResponse(
        "budgets.html",
        {
            "request": request,
            "current_phase": phase,
            "version": settings.version,
            "budgets": budgets,
            "total_budgets": total,
            "warn_budgets": warn_list,
            "danger_budgets": danger_list,
            # alerts_count reused in nav (only include active ones)
            "alerts_count": len(warn_list) + len(danger_list),
        },
    )


@router.get("/ui/forex", response_class=HTMLResponse)
async def ui_forex(request: Request, db: Database = Depends(get_db)):
    """Forex cards overview (T10.02 low balance logic UI).

    Displays each forex card with remaining balance and highlights low balance
    (<20% remaining) without reimplementing business logic.
    """
    phase = compute_phase(db)
    settings = get_settings()
    rows = db.list_forex_cards()
    cards = list_forex_status(rows)
    low_cards = [c for c in cards if c["low_balance"]]
    return templates.TemplateResponse(
        "forex.html",
        {
            "request": request,
            "current_phase": phase,
            "version": settings.version,
            "cards": cards,
            "low_cards": low_cards,
            "alerts_count": len(low_cards),  # for nav badge consistency
        },
    )


@router.get("/ui/alerts", response_class=HTMLResponse)
async def ui_alerts(request: Request, db: Database = Depends(get_db)):
    """Alerts overview (T10.03) - consolidates current active alerts.

    Reuses `_alerts.html` partial for list rendering to ensure consistency with
    the dashboard. Provides a simple dedicated page for quick scanning.
    """
    phase = compute_phase(db)
    settings = get_settings()
    alerts = collect_alerts(db)
    return templates.TemplateResponse(
        "alerts.html",
        {
            "request": request,
            "current_phase": phase,
            "version": settings.version,
            "alerts": alerts,
            "alerts_count": len(alerts),
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


@router.get("/ui/expenses", response_class=HTMLResponse)
async def ui_expenses_list(request: Request, db: Database = Depends(get_db)):
    phase = compute_phase(db)
    settings = get_settings()
    rows = db.list_expenses()
    grouped = group_expenses_by_date(rows)

    return templates.TemplateResponse(
        "expenses_list.html",
        {
            "request": request,
            "current_phase": phase,
            "version": settings.version,
            "expenses": grouped,
        },
    )


def _build_expense_form_context(
    request: Request,
    phase: str,
    version: str,
    errors: List[str],
    form_state: dict,
    success: bool = False,
    expense_id: Optional[int] = None,
    updated: bool = False,
):
    return {
        "request": request,
        "current_phase": phase,
        "version": version,
        "currencies": sorted(CURRENCIES),
        "categories": sorted(CATEGORIES),
        "payment_methods": sorted(PAYMENT_METHODS),
        "errors": errors,
        "form": form_state,
        "success": success,
        "expense_id": expense_id,
        "updated": updated,
        "editing": expense_id is not None,
    }


def group_expenses_by_date(rows: List[dict]):
    """Group expense rows by date (descending as provided) computing per-day INR total.

    Expects rows already ordered by date DESC, id DESC (as returned by DAL list_expenses).
    Returns list of {date, entries: [...], day_total_inr} preserving ordering.
    """
    grouped: List[dict] = []
    current_bucket: Optional[dict] = None
    current_date: Optional[str] = None
    day_total = 0.0
    for r in rows:
        d = r["date"]
        if d != current_date:
            if current_bucket is not None:
                current_bucket["day_total_inr"] = round2(day_total)
                grouped.append(current_bucket)
            current_date = d
            current_bucket = {"date": d, "entries": [], "day_total_inr": 0.0}
            day_total = 0.0
        current_bucket["entries"].append(r)
        try:
            day_total += float(r.get("inr_equivalent", 0.0))
        except Exception:  # pragma: no cover - defensive
            pass
    if current_bucket is not None:
        current_bucket["day_total_inr"] = round2(day_total)
        grouped.append(current_bucket)
    return grouped


@router.get("/ui/expenses/{expense_id}/edit", response_class=HTMLResponse)
async def ui_expense_edit_form(
    request: Request, expense_id: int, db: Database = Depends(get_db)
):
    phase = compute_phase(db)
    settings = get_settings()
    row = db.get_expense(expense_id)
    if not row:
        raise HTTPException(status_code=404, detail="Expense not found")
    form_state = {
        "amount": row["amount"],
        "currency": row["currency"],
        "category": row["category"],
        "payment_method": row["payment_method"],
        "date": row["date"],
        "description": row.get("description"),
    }
    ctx = _build_expense_form_context(
        request,
        phase,
        settings.version,
        errors=[],
        form_state=form_state,
        expense_id=expense_id,
    )
    return templates.TemplateResponse("expense_form.html", ctx)


@router.post("/ui/expenses/{expense_id}/edit", response_class=HTMLResponse)
async def ui_expense_edit_submit(
    request: Request,
    expense_id: int,
    amount: float = Form(...),
    category: str = Form(...),
    payment_method: str = Form(...),
    date: str = Form(...),
    description: str | None = Form(None),
    db: Database = Depends(get_db),
):
    phase = compute_phase(db)
    settings = get_settings()
    row = db.get_expense(expense_id)
    if not row:
        raise HTTPException(status_code=404, detail="Expense not found")
    errors: List[str] = []

    # Immutable currency (enforced by form absence) - we reuse existing
    currency = row["currency"]

    from datetime import date as date_cls

    try:
        parsed_date = date_cls.fromisoformat(date)
    except ValueError:
        errors.append("Invalid date format")
        parsed_date = None

    # Build update model (partial fields allowed but we supply all)
    if parsed_date:
        try:
            update_in = ExpenseUpdateIn(
                amount=amount,
                category=category,
                description=description if description else None,
                date=parsed_date,
                payment_method=payment_method,
            )
            # Domain validation again using temporary full object concept
            temp_full = ExpenseIn(
                amount=amount,
                currency=currency,
                category=category,
                description=description if description else None,
                date=parsed_date,
                payment_method=payment_method,
            )
            validate_expense_domain(temp_full)
        except ValidationError as ve:
            for err in ve.errors():
                loc = ".".join([str(p) for p in err.get("loc", [])])
                msg = err.get("msg", "invalid")
                errors.append(f"{loc}: {msg}")
        except HTTPException as he:
            errors.append(he.detail)
        except Exception:
            errors.append("Unexpected validation error")
    else:
        update_in = None

    updated = False
    if not errors and update_in:
        try:
            # Compute new INR equivalent & rate
            rate_service = get_central_rate_cache_service()
            conv = compute_inr_equivalent(amount, currency, rate_service)
            budget_delta = amount - float(row["amount"])
            db.update_expense_with_budget(
                expense_id=expense_id,
                new_amount=amount,
                new_category=category,
                new_description=description if description else None,
                new_date=parsed_date,
                new_payment_method=payment_method,
                new_inr_equivalent=conv.inr_equivalent,
                new_exchange_rate=conv.rate,
                budget_delta=budget_delta,
            )
            updated = True
            # Refresh row
            row = db.get_expense(expense_id) or row
        except Exception:
            errors.append("Failed to update expense")

    form_state = {
        "amount": row["amount"],
        "currency": row["currency"],
        "category": row["category"],
        "payment_method": row["payment_method"],
        "date": row["date"],
        "description": row.get("description"),
    }

    ctx = _build_expense_form_context(
        request,
        phase,
        settings.version,
        errors=errors,
        form_state=form_state,
        success=False,
        expense_id=expense_id,
        updated=updated,
    )
    return templates.TemplateResponse("expense_form.html", ctx)


@router.post("/ui/expenses/{expense_id}/delete", response_class=HTMLResponse)
async def ui_expense_delete(
    request: Request, expense_id: int, db: Database = Depends(get_db)
):
    # Perform delete then redirect via simple HTML (no redirect helper to keep minimal deps)
    try:
        db.delete_expense_with_budget(expense_id)
    except Exception:
        # ignore errors to keep idempotent feel
        pass
    # After deletion route back to list
    phase = compute_phase(db)
    settings = get_settings()
    rows = db.list_expenses()
    grouped = group_expenses_by_date(rows)

    return templates.TemplateResponse(
        "expenses_list.html",
        {
            "request": request,
            "current_phase": phase,
            "version": settings.version,
            "expenses": grouped,
            "deleted_id": expense_id,
        },
    )
