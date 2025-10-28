from __future__ import annotations

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.config import get_settings
from app.db.dal import Database
from app.services.analytics_utils import (
    compute_average_daily_spend,
    compute_remaining_daily_budget,
    compute_currency_breakdown,
    compute_category_breakdown,
    compute_trend_data,
)
from app.services.trip_context import get_active_trip_id, clear_trip_context

router = APIRouter(prefix="/analytics", tags=["analytics"])


def get_db() -> Database:
    settings = get_settings()
    return Database(settings.db_path)


class DailyTotal(BaseModel):
    date: date
    total_inr: float


class AverageDailySpend(BaseModel):
    total_inr: float
    days_elapsed: int
    average_daily_spend: float


class RemainingDailyBudget(BaseModel):
    remaining_inr: float
    days_left: int
    remaining_daily_budget: float


class CurrencyBreakdownItem(BaseModel):
    currency: str
    amount_total: float
    inr_total: float
    percent_inr: float


class CategoryBreakdownItem(BaseModel):
    category: str
    inr_total: float
    percent: float


class TrendPoint(BaseModel):
    date: date
    daily_total_inr: float
    cumulative_total_inr: float


@router.get(
    "/daily-totals",
    response_model=List[DailyTotal],
    summary="Daily INR totals (optionally filtered by date range)",
)
async def daily_totals_endpoint(
    start_date: Optional[date] = Query(None, description="Filter start date inclusive"),
    end_date: Optional[date] = Query(None, description="Filter end date inclusive"),
    trip_id: Optional[int] = Query(
        None, description="Trip identifier (defaults to active trip)"
    ),
    db: Database = Depends(get_db),
):
    """Return aggregated INR totals per day ordered ascending by date.

    MVP semantics:
    - If only end_date provided ensure it's not before start_date when both present.
    - Empty result if start_date > end_date.
    - No phase filtering here (timeline already expressed in raw expenses if needed).
    """
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=400, detail="start_date cannot be after end_date"
        )
    clear_trip_context()
    resolved_trip = trip_id if trip_id is not None else get_active_trip_id(db)
    rows = db.daily_totals(
        start_date=start_date, end_date=end_date, trip_id=resolved_trip
    )
    # DAL returns keys: day, total_inr
    return [DailyTotal(date=r["day"], total_inr=r["total_inr"]) for r in rows]


@router.get(
    "/average-daily-spend",
    response_model=AverageDailySpend,
    summary="Average daily spend (total INR / days elapsed)",
)
async def average_daily_spend_endpoint(
    as_of: Optional[date] = Query(
        None, description="Optional 'as of' date (defaults to today)"
    ),
    trip_id: Optional[int] = Query(
        None, description="Trip identifier (defaults to active trip)"
    ),
    db: Database = Depends(get_db),
):
    """Compute average daily spend since earliest expense date up to as_of (inclusive).

    If there are no expenses returns zeros. Days elapsed counts inclusive span.
    """
    clear_trip_context()
    resolved_trip = trip_id if trip_id is not None else get_active_trip_id(db)
    result = compute_average_daily_spend(db, as_of=as_of, trip_id=resolved_trip)
    return AverageDailySpend(
        total_inr=result.total_inr,
        days_elapsed=result.days_elapsed,
        average_daily_spend=result.average_daily_spend,
    )


@router.get(
    "/remaining-daily-budget",
    response_model=RemainingDailyBudget,
    summary="Remaining daily budget (remaining INR / days left including today)",
)
async def remaining_daily_budget_endpoint(
    as_of: Optional[date] = Query(
        None, description="Optional 'as of' date (defaults to today)"
    ),
    trip_id: Optional[int] = Query(
        None, description="Trip identifier (defaults to active trip)"
    ),
    db: Database = Depends(get_db),
):
    """Compute remaining daily budget based on INR budget and trip dates.

    If trip dates not configured or trip already ended relative to as_of, returns zeros.
    days_left includes the as_of date and trip end date.
    """
    clear_trip_context()
    resolved_trip = trip_id if trip_id is not None else get_active_trip_id(db)
    result = compute_remaining_daily_budget(db, as_of=as_of, trip_id=resolved_trip)
    return RemainingDailyBudget(
        remaining_inr=result.remaining_inr,
        days_left=result.days_left,
        remaining_daily_budget=result.remaining_daily_budget,
    )


@router.get(
    "/currency-breakdown",
    response_model=List[CurrencyBreakdownItem],
    summary="Totals per currency with INR percentage",
)
async def currency_breakdown_endpoint(
    start_date: Optional[date] = Query(None, description="Filter start date inclusive"),
    end_date: Optional[date] = Query(None, description="Filter end date inclusive"),
    trip_id: Optional[int] = Query(
        None, description="Trip identifier (defaults to active trip)"
    ),
    db: Database = Depends(get_db),
):
    """Return per-currency totals and percent of overall INR total.

    Percent is based on INR equivalents (already stored per expense) so no
    recomputation or rate lookup needed. If total INR is 0, all percents = 0.
    """
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=400, detail="start_date cannot be after end_date"
        )
    clear_trip_context()
    resolved_trip = trip_id if trip_id is not None else get_active_trip_id(db)
    items = compute_currency_breakdown(
        db, start_date=start_date, end_date=end_date, trip_id=resolved_trip
    )
    return [
        CurrencyBreakdownItem(
            currency=i.currency,
            amount_total=i.amount_total,
            inr_total=i.inr_total,
            percent_inr=i.percent_inr,
        )
        for i in items
    ]


@router.get(
    "/category-breakdown",
    response_model=List[CategoryBreakdownItem],
    summary="Totals per category with percent of total",
)
async def category_breakdown_endpoint(
    start_date: Optional[date] = Query(None, description="Filter start date inclusive"),
    end_date: Optional[date] = Query(None, description="Filter end date inclusive"),
    trip_id: Optional[int] = Query(
        None, description="Trip identifier (defaults to active trip)"
    ),
    db: Database = Depends(get_db),
):
    """Return per-category INR totals and percent of grand total.

    Percent values originate from DAL (already rounded) to keep consistency with
    currency breakdown rounding approach.
    """
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=400, detail="start_date cannot be after end_date"
        )
    clear_trip_context()
    resolved_trip = trip_id if trip_id is not None else get_active_trip_id(db)
    items = compute_category_breakdown(
        db, start_date=start_date, end_date=end_date, trip_id=resolved_trip
    )
    return [
        CategoryBreakdownItem(
            category=i.category, inr_total=i.inr_total, percent=i.percent
        )
        for i in items
    ]


@router.get(
    "/trend",
    response_model=List[TrendPoint],
    summary="Daily totals plus cumulative INR spend (trend)",
)
async def trend_endpoint(
    start_date: Optional[date] = Query(None, description="Filter start date inclusive"),
    end_date: Optional[date] = Query(None, description="Filter end date inclusive"),
    trip_id: Optional[int] = Query(
        None, description="Trip identifier (defaults to active trip)"
    ),
    db: Database = Depends(get_db),
):
    """Return ordered daily INR totals with cumulative sum for charting.

    Useful for line/area charts showing progression vs time. Empty list if no
    expenses in the (optional) filtered range. Cumulative values are rounded
    using shared round2 logic encapsulated in compute_trend_data.
    """
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=400, detail="start_date cannot be after end_date"
        )
    clear_trip_context()
    resolved_trip = trip_id if trip_id is not None else get_active_trip_id(db)
    points = compute_trend_data(
        db, start_date=start_date, end_date=end_date, trip_id=resolved_trip
    )
    return [
        TrendPoint(
            date=p.date,
            daily_total_inr=p.daily_total_inr,
            cumulative_total_inr=p.cumulative_total_inr,
        )
        for p in points
    ]
