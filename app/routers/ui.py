from datetime import date
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, Request, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from app.core.config import get_settings
from app.db.dal import Database
from app.services.timeline import get_trip_dates, resolve_phase
from app.services.budget_utils import list_budget_statuses
from app.services.forex_utils import list_status as list_forex_status
from app.services.alerts import collect_alerts
from app.services.settings import get_thresholds, set_thresholds
from app.services.app_settings import (
    get_effective_rate_provider,
    set_rate_provider,
    get_rates_cache_ttl,
    set_rates_cache_ttl,
    get_budget_enforce_cap,
    set_budget_enforce_cap,
    get_budget_auto_create,
    set_budget_auto_create,
    get_default_budget_amounts,
    set_default_budget_amount,
    get_ui_theme,
    set_ui_theme,
    get_ui_show_day_totals,
    set_ui_show_day_totals,
    get_ui_expense_layout,
    set_ui_expense_layout,
    get_widget_flag,
    set_widget_flag,
)
from app.models.constants import FOREX_CURRENCIES
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
from app.services.trip_context import get_active_trip_id, clear_trip_context

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


def _trip_nav_context(db: Database, trip_id: Optional[int] = None) -> Dict[str, Any]:
    tid = trip_id if trip_id is not None else get_active_trip_id(db)
    trip_rows = db.list_trips(include_archived=True)
    trips: List[Dict[str, Any]] = []
    for row in trip_rows:
        trips.append(
            {
                "id": int(row["id"]),
                "name": row.get("name", ""),
                "status": row.get("status", "active"),
                "start_date": row.get("start_date"),
                "end_date": row.get("end_date"),
            }
        )
    active = next((t for t in trips if t["id"] == tid), None)
    return {
        "active_trip": active,
        "active_trip_id": tid,
        "trip_options": trips,
    }


@router.get("/ui", response_class=HTMLResponse)
async def ui_home(request: Request, db: Database = Depends(get_db)):
    clear_trip_context()
    phase = compute_phase(db)
    settings = get_settings()
    trip_id = get_active_trip_id(db)

    # Metrics
    budgets = list_budget_statuses(db, trip_id=trip_id)
    avg = compute_average_daily_spend(db, trip_id=trip_id)
    remaining = compute_remaining_daily_budget(db, trip_id=trip_id)
    currency_breakdown = compute_currency_breakdown(db, trip_id=trip_id)
    category_breakdown = compute_category_breakdown(db, trip_id=trip_id)

    rate_service = get_central_rate_cache_service()
    rates = []
    for cur in ("SGD", "MYR"):
        try:
            rate = rate_service.get_rate(cur)
            rates.append({"currency": cur, "rate": rate})
        except Exception:
            rates.append({"currency": cur, "rate": "-"})

    # Alerts aggregation via centralized service (T10.03)
    alerts = collect_alerts(db, trip_id=trip_id)

    context = {
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
    }
    context.update(_trip_nav_context(db, trip_id=trip_id))
    return templates.TemplateResponse("dashboard.html", context)


@router.get("/ui/budgets", response_class=HTMLResponse)
async def ui_budgets(request: Request, db: Database = Depends(get_db)):
    """Standalone budgets page (T10.01) highlighting threshold logic.

    Reuses existing budget status utility that already exposes 80% / 90% flags.
    Provides an at-a-glance view plus simple legend without duplicating logic
    implemented in dashboard.
    """
    clear_trip_context()
    phase = compute_phase(db)
    settings = get_settings()
    trip_id = get_active_trip_id(db)
    budgets = list_budget_statuses(db, trip_id=trip_id)

    # Derive counts for thresholds (purely presentational)
    total = len(budgets)
    warn_list = [b for b in budgets if b["eighty"] and not b["ninety"]]
    danger_list = [b for b in budgets if b["ninety"]]
    alerts = collect_alerts(db, trip_id=trip_id)

    context = {
        "request": request,
        "current_phase": phase,
        "version": settings.version,
        "budgets": budgets,
        "total_budgets": total,
        "warn_budgets": warn_list,
        "danger_budgets": danger_list,
        "alerts_count": len(alerts),
    }
    context.update(_trip_nav_context(db, trip_id=trip_id))
    return templates.TemplateResponse("budgets.html", context)


@router.get("/ui/forex", response_class=HTMLResponse)
async def ui_forex(request: Request, db: Database = Depends(get_db)):
    """Forex cards overview (T10.02 low balance logic UI).

    Displays each forex card with remaining balance and highlights low balance
    (<20% remaining) without reimplementing business logic.
    """
    clear_trip_context()
    phase = compute_phase(db)
    settings = get_settings()
    trip_id = get_active_trip_id(db)
    rows = db.list_forex_cards(trip_id=trip_id)
    thresholds = get_thresholds(db)
    cards = list_forex_status(rows, forex_low_pct=thresholds.forex_low)
    low_cards = [c for c in cards if c["low_balance"]]
    alerts = collect_alerts(db, trip_id=trip_id)
    context = {
        "request": request,
        "current_phase": phase,
        "version": settings.version,
        "cards": cards,
        "low_cards": low_cards,
        "alerts_count": len(alerts),
    }
    context.update(_trip_nav_context(db, trip_id=trip_id))
    return templates.TemplateResponse("forex.html", context)


@router.get("/ui/alerts", response_class=HTMLResponse)
async def ui_alerts(request: Request, db: Database = Depends(get_db)):
    """Alerts overview (T10.03) - consolidates current active alerts.

    Reuses `_alerts.html` partial for list rendering to ensure consistency with
    the dashboard. Provides a simple dedicated page for quick scanning.
    """
    clear_trip_context()
    phase = compute_phase(db)
    settings = get_settings()
    trip_id = get_active_trip_id(db)
    alerts = collect_alerts(db, trip_id=trip_id)
    context = {
        "request": request,
        "current_phase": phase,
        "version": settings.version,
        "alerts": alerts,
        "alerts_count": len(alerts),
        }
    context.update(_trip_nav_context(db, trip_id=trip_id))
    return templates.TemplateResponse("alerts.html", context)


@router.post("/ui/trips/select", response_class=RedirectResponse)
async def ui_trip_select(
    trip_id: int = Form(...),
    next_url: Optional[str] = Form(None),
    db: Database = Depends(get_db),
):
    try:
        db.set_active_trip(trip_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Trip not found")
    clear_trip_context()
    target = next_url or "/ui"
    if not target.startswith("/"):
        target = "/ui"
    return RedirectResponse(url=target, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/ui/expenses/new", response_class=HTMLResponse)
async def ui_expense_form(request: Request, db: Database = Depends(get_db)):
    clear_trip_context()
    phase = compute_phase(db)
    settings = get_settings()
    trip_id = get_active_trip_id(db)
    # Initial blank form data
    form = {}
    context = {
        "request": request,
        "current_phase": phase,
        "version": settings.version,
        "currencies": sorted(CURRENCIES),
        "categories": sorted(CATEGORIES),
        "payment_methods": sorted(PAYMENT_METHODS),
        "errors": [],
        "form": form,
        "success": False,
    }
    context.update(_trip_nav_context(db, trip_id=trip_id))
    return templates.TemplateResponse("expense_form.html", context)


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
    clear_trip_context()
    phase = compute_phase(db)
    settings = get_settings()
    trip_id = get_active_trip_id(db)
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
                trip_id=trip_id,
            )
            row = db.get_expense(expense_id, trip_id=trip_id)
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

    context = {
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
    }
    context.update(_trip_nav_context(db, trip_id=trip_id))
    return templates.TemplateResponse("expense_form.html", context)


@router.get("/ui/expenses", response_class=HTMLResponse)
async def ui_expenses_list(request: Request, db: Database = Depends(get_db)):
    clear_trip_context()
    phase = compute_phase(db)
    settings = get_settings()
    trip_id = get_active_trip_id(db)
    rows = db.list_expenses(trip_id=trip_id)
    grouped = group_expenses_by_date(rows)

    context = {
        "request": request,
        "current_phase": phase,
        "version": settings.version,
        "expenses": grouped,
    }
    context.update(_trip_nav_context(db, trip_id=trip_id))
    return templates.TemplateResponse("expenses_list.html", context)


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


@router.get("/ui/settings", response_class=HTMLResponse)
async def ui_settings(request: Request, db: Database = Depends(get_db)):
    """Settings page for trip dates, dynamic thresholds, and forex loads.

    Displays current values with forms for each logical section. POST handler
    re-renders same template with success/error messages.
    """
    clear_trip_context()
    phase = compute_phase(db)
    settings = get_settings()
    trip_id = get_active_trip_id(db)
    alerts = collect_alerts(db, trip_id=trip_id)
    trip_dates = db.get_trip_dates(trip_id=trip_id)
    th = get_thresholds(db)
    existing_rows = {
        r["currency"]: r
        for r in db.list_forex_cards(trip_id=trip_id)
        if r["currency"] in FOREX_CURRENCIES
    }
    # Ensure all supported forex currencies appear with default placeholders
    forex_rows = {}
    for cur in sorted(FOREX_CURRENCIES):
        forex_rows[cur] = existing_rows.get(
            cur,
            {"currency": cur, "loaded_amount": 0.0, "spent_amount": 0.0},
        )
    # Additional dynamic settings context
    rate_provider = get_effective_rate_provider(db)
    rate_ttl = get_rates_cache_ttl(db)
    budget_flags = {
        "enforce_cap": get_budget_enforce_cap(db),
        "auto_create": get_budget_auto_create(db),
        "defaults": get_default_budget_amounts(db),
    }
    ui_prefs = {
        "theme": get_ui_theme(db),
        "show_day_totals": get_ui_show_day_totals(db),
        "expense_layout": get_ui_expense_layout(db),
        "widgets": {
            "budgets": get_widget_flag(db, "budgets", True),
            "rates": get_widget_flag(db, "rates", True),
            "categories": get_widget_flag(db, "categories", True),
            "currencies": get_widget_flag(db, "currencies", True),
        },
    }
    context = {
        "request": request,
        "current_phase": phase,
        "version": settings.version,
        "alerts_count": len(alerts),
        "trip_dates": trip_dates,
        "thresholds": th,
        "forex_rows": forex_rows,
        "messages": {},
        "errors": {},
        "rate_provider": rate_provider,
        "rate_ttl": rate_ttl,
        "budget_flags": budget_flags,
        "ui_prefs": ui_prefs,
    }
    context.update(_trip_nav_context(db, trip_id=trip_id))
    return templates.TemplateResponse("settings.html", context)


@router.post("/ui/settings", response_class=HTMLResponse)
async def ui_settings_submit(request: Request, db: Database = Depends(get_db)):
    clear_trip_context()
    phase = compute_phase(db)
    settings = get_settings()
    trip_id = get_active_trip_id(db)
    form = await request.form()
    section = form.get("section", "").strip()
    messages: dict[str, list[str]] = {}
    errors: dict[str, list[str]] = {}
    # trip_id already resolved above for reuse

    # Trip dates --------------------------------------------------
    if section == "trip_dates":
        start_raw = form.get("start_date") or ""
        end_raw = form.get("end_date") or ""
        import datetime as _dt

        try:
            start_d = _dt.date.fromisoformat(start_raw)
            end_d = _dt.date.fromisoformat(end_raw)
            if end_d < start_d:
                raise ValueError("End date must be >= start date")
            db.set_trip_dates(start_d, end_d, trip_id=trip_id)
            messages.setdefault("trip_dates", []).append("Trip dates updated")
        except Exception as exc:  # pragma: no cover (UI validation path)
            errors.setdefault("trip_dates", []).append(str(exc) or "Invalid trip dates")

    # Thresholds --------------------------------------------------
    elif section == "thresholds":
        try:
            budget_warn = int(form.get("budget_warn", ""))
            budget_danger = int(form.get("budget_danger", ""))
            forex_low = int(form.get("forex_low", ""))
            set_thresholds(db, budget_warn, budget_danger, forex_low)
            messages.setdefault("thresholds", []).append("Thresholds updated")
        except ValueError as ve:
            errors.setdefault("thresholds", []).append(str(ve))
        except Exception:  # pragma: no cover
            errors.setdefault("thresholds", []).append("Failed to update thresholds")

    # Forex loads -------------------------------------------------
    elif section == "forex_loads":
        updated_any = False
        for cur in sorted(FOREX_CURRENCIES):
            key = f"loaded_{cur}"
            if key in form and form.get(key) != "":
                try:
                    val = float(form.get(key))
                    if val < 0:
                        raise ValueError("Loaded amount cannot be negative")
                    db.set_forex_card_loaded(cur, val, trip_id=trip_id)
                    updated_any = True
                except Exception as exc:
                    errors.setdefault("forex_loads", []).append(f"{cur}: {exc}")
        if updated_any and "forex_loads" not in errors:
            messages.setdefault("forex_loads", []).append("Forex loads updated")
        if not updated_any and "forex_loads" not in errors:
            errors.setdefault("forex_loads", []).append("No forex values provided")

    # New sections ----------------------------------------------
    elif section == "rate_settings":
        try:
            provider = form.get("rate_provider", "").strip()
            ttl_raw = form.get("rates_cache_ttl", "").strip()
            if provider:
                set_rate_provider(db, provider)
                messages.setdefault("rate_settings", []).append("Rate provider updated")
            if ttl_raw:
                set_rates_cache_ttl(db, int(ttl_raw))
                messages.setdefault("rate_settings", []).append("Cache TTL updated")
        except ValueError as ve:
            errors.setdefault("rate_settings", []).append(str(ve))
        except Exception:
            errors.setdefault("rate_settings", []).append(
                "Failed to update rate settings"
            )
    elif section == "budget_settings":
        try:
            enforce = form.get("budget_enforce_cap") == "on"
            auto_create = form.get("budget_auto_create") == "on"
            set_budget_enforce_cap(db, enforce)
            set_budget_auto_create(db, auto_create)
            # Optional default budget inputs pattern: default_budget_<CUR>
            for k, v in form.items():
                if k.startswith("default_budget_") and v.strip() != "":
                    cur = k.split("default_budget_")[-1].upper()
                    try:
                        amt = float(v)
                        set_default_budget_amount(db, cur, amt)
                    except Exception as exc:  # accumulate but continue
                        errors.setdefault("budget_settings", []).append(f"{cur}: {exc}")
            if "budget_settings" not in errors:
                messages.setdefault("budget_settings", []).append(
                    "Budget settings updated"
                )
        except Exception as exc:
            errors.setdefault("budget_settings", []).append(
                str(exc) or "Failed budget settings"
            )
    elif section == "ui_preferences":
        try:
            theme = form.get("ui_theme", "auto")
            layout = form.get("ui_expense_layout", "detailed")
            show_day_totals = form.get("ui_show_day_totals") == "on"
            set_ui_theme(db, theme)
            set_ui_expense_layout(db, layout)
            set_ui_show_day_totals(db, show_day_totals)
            for w in ("budgets", "rates", "categories", "currencies"):
                set_widget_flag(db, w, form.get(f"widget_{w}") == "on")
            messages.setdefault("ui_preferences", []).append("UI preferences updated")
        except ValueError as ve:
            errors.setdefault("ui_preferences", []).append(str(ve))
        except Exception:
            errors.setdefault("ui_preferences", []).append(
                "Failed to update UI preferences"
            )
    elif section == "reset_trip":
        from app.services.reset_utils import reset_trip_data

        confirm = form.get("confirm_reset") == "on"
        token = (form.get("confirm_token") or "").strip().lower()
        preserve = form.get("preserve_settings") == "on"
        if not confirm or token != "reset":
            errors.setdefault("reset_trip", []).append(
                "Confirmation required: tick the box and type 'reset'"
            )
        else:
            try:
                reset_trip_data(db, preserve_settings=preserve, trip_id=trip_id)
                clear_trip_context()
                messages.setdefault("reset_trip", []).append(
                    "Trip data cleared. Configure new trip dates to begin."
                )
            except Exception as exc:
                errors.setdefault("reset_trip", []).append(str(exc) or "Reset failed")

    # Refresh state after potential mutations (shared) -----------
    trip_id = get_active_trip_id(db)
    trip_dates = db.get_trip_dates(trip_id=trip_id)
    th = get_thresholds(db)
    existing_rows = {
        r["currency"]: r
        for r in db.list_forex_cards(trip_id=trip_id)
        if r["currency"] in FOREX_CURRENCIES
    }
    forex_rows = {}
    for cur in sorted(FOREX_CURRENCIES):
        forex_rows[cur] = existing_rows.get(
            cur,
            {"currency": cur, "loaded_amount": 0.0, "spent_amount": 0.0},
        )

    rate_provider = get_effective_rate_provider(db)
    rate_ttl = get_rates_cache_ttl(db)
    budget_flags = {
        "enforce_cap": get_budget_enforce_cap(db),
        "auto_create": get_budget_auto_create(db),
        "defaults": get_default_budget_amounts(db),
    }
    ui_prefs = {
        "theme": get_ui_theme(db),
        "show_day_totals": get_ui_show_day_totals(db),
        "expense_layout": get_ui_expense_layout(db),
        "widgets": {
            "budgets": get_widget_flag(db, "budgets", True),
            "rates": get_widget_flag(db, "rates", True),
            "categories": get_widget_flag(db, "categories", True),
            "currencies": get_widget_flag(db, "currencies", True),
        },
    }
    alerts = collect_alerts(db, trip_id=trip_id)

    context = {
        "request": request,
        "current_phase": phase,
        "version": settings.version,
        "alerts_count": len(alerts),
        "trip_dates": trip_dates,
        "thresholds": th,
        "forex_rows": forex_rows,
        "messages": messages,
        "errors": errors,
        "active_section": section,
        "rate_provider": rate_provider,
        "rate_ttl": rate_ttl,
        "budget_flags": budget_flags,
        "ui_prefs": ui_prefs,
    }
    context.update(_trip_nav_context(db, trip_id=trip_id))
    return templates.TemplateResponse("settings.html", context)


@router.get("/ui/expenses/{expense_id}/edit", response_class=HTMLResponse)
async def ui_expense_edit_form(
    request: Request, expense_id: int, db: Database = Depends(get_db)
):
    clear_trip_context()
    phase = compute_phase(db)
    settings = get_settings()
    trip_id = get_active_trip_id(db)
    row = db.get_expense(expense_id, trip_id=trip_id)
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
    ctx.update(_trip_nav_context(db, trip_id=trip_id))
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
    clear_trip_context()
    phase = compute_phase(db)
    settings = get_settings()
    trip_id = get_active_trip_id(db)
    row = db.get_expense(expense_id, trip_id=trip_id)
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
                trip_id=trip_id,
            )
            updated = True
            # Refresh row
            row = db.get_expense(expense_id, trip_id=trip_id) or row
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
    ctx.update(_trip_nav_context(db, trip_id=trip_id))
    return templates.TemplateResponse("expense_form.html", ctx)


@router.post("/ui/expenses/{expense_id}/delete", response_class=HTMLResponse)
async def ui_expense_delete(
    request: Request, expense_id: int, db: Database = Depends(get_db)
):
    # Perform delete then redirect via simple HTML (no redirect helper to keep minimal deps)
    clear_trip_context()
    trip_id = get_active_trip_id(db)
    try:
        db.delete_expense_with_budget(expense_id, trip_id=trip_id)
    except Exception:
        # ignore errors to keep idempotent feel
        pass
    # After deletion route back to list
    phase = compute_phase(db)
    settings = get_settings()
    rows = db.list_expenses(trip_id=trip_id)
    grouped = group_expenses_by_date(rows)

    context = {
        "request": request,
        "current_phase": phase,
        "version": settings.version,
        "expenses": grouped,
        "deleted_id": expense_id,
    }
    context.update(_trip_nav_context(db, trip_id=trip_id))
    return templates.TemplateResponse("expenses_list.html", context)
