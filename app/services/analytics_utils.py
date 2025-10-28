from __future__ import annotations

from datetime import date
from dataclasses import dataclass

from app.db.dal import Database
from app.services.money import round2
from app.services.budget_utils import get_budget_status

"""Analytics helper utilities (T08.02, T08.03, T08.04, T08.05, T08.06).

Scopes implemented:
    - Average daily spend (T08.02)
    - Remaining daily budget (T08.03)
    - Currency breakdown (T08.04)
    - Category breakdown (T08.05)
    - Trend data (daily cumulative) (T08.06)

Design notes:
    Keep computations isolated & pure (DB dependency injected) for easy unit
    testing and later reuse in templated dashboard views.
"""


@dataclass(frozen=True)
class AverageDailySpendResult:
    total_inr: float
    days_elapsed: int
    average_daily_spend: float


def compute_average_daily_spend(
    db: Database, as_of: date | None = None, trip_id: int | None = None
) -> AverageDailySpendResult:
    as_of = as_of or date.today()
    tid = trip_id if trip_id is not None else db.get_active_trip_id()
    earliest = db.earliest_expense_date(trip_id=tid)
    if earliest is None or earliest > as_of:
        return AverageDailySpendResult(
            total_inr=0.0, days_elapsed=0, average_daily_spend=0.0
        )
    total = db.total_inr_spent(trip_id=tid)
    days_elapsed = (as_of - earliest).days + 1  # inclusive span
    if days_elapsed <= 0:
        days_elapsed = 1
    avg = round2(total / days_elapsed) if total > 0 else 0.0
    return AverageDailySpendResult(
        total_inr=total, days_elapsed=days_elapsed, average_daily_spend=avg
    )


# ---------------- Remaining Daily Budget (T08.03) -----------------
@dataclass(frozen=True)
class RemainingDailyBudgetResult:
    remaining_inr: float
    days_left: int
    remaining_daily_budget: float


def compute_remaining_daily_budget(
    db: Database, as_of: date | None = None, trip_id: int | None = None
) -> RemainingDailyBudgetResult:
    """Compute remaining daily budget for the rest of the trip.

    Definitions (MVP assumptions):
        - We treat INR budget as the master aggregate budget.
        - remaining_inr = max_amount - spent_amount from INR budget status (0 if missing).
        - Trip dates must be configured; if not, return zeros.
        - days_left = number of calendar days from as_of (default today) through trip_end inclusive.
        - If as_of > trip_end, days_left = 0 and remaining_daily_budget = 0.
        - If days_left <= 0 OR remaining_inr <= 0 => remaining_daily_budget = 0.

    Edge Cases:
        - Missing INR budget row -> treat remaining_inr=0.
        - Negative remaining (should not occur due to clamping) -> clamp to 0.
    """
    as_of = as_of or date.today()
    tid = trip_id if trip_id is not None else db.get_active_trip_id()
    trip = db.get_trip_dates(trip_id=tid)
    if not trip:
        return RemainingDailyBudgetResult(
            remaining_inr=0.0, days_left=0, remaining_daily_budget=0.0
        )
    end_date = trip["end_date"]
    if as_of > end_date:
        return RemainingDailyBudgetResult(
            remaining_inr=0.0, days_left=0, remaining_daily_budget=0.0
        )
    days_left = (end_date - as_of).days + 1  # inclusive of today & end_date
    if days_left <= 0:
        return RemainingDailyBudgetResult(
            remaining_inr=0.0, days_left=0, remaining_daily_budget=0.0
        )
    inr_status = get_budget_status(db, "INR", trip_id=tid)
    remaining_inr = float(inr_status["remaining"]) if inr_status else 0.0
    if remaining_inr <= 0:
        return RemainingDailyBudgetResult(
            remaining_inr=0.0, days_left=days_left, remaining_daily_budget=0.0
        )
    per_day = round2(remaining_inr / days_left)
    return RemainingDailyBudgetResult(
        remaining_inr=remaining_inr,
        days_left=days_left,
        remaining_daily_budget=per_day,
    )


# ---------------- Currency Breakdown (T08.04) -----------------
@dataclass(frozen=True)
class CurrencyBreakdownItem:
    currency: str
    amount_total: float
    inr_total: float
    percent_inr: float


def compute_currency_breakdown(
    db: Database,
    start_date: date | None = None,
    end_date: date | None = None,
    trip_id: int | None = None,
) -> list[CurrencyBreakdownItem]:
    """Return list of currency breakdown items ordered by currency.

    Leverages DAL `sums_by_currency` which returns rows with keys:
        - currency
        - amount_total (sum of original amounts)
        - inr_total (sum of inr_equivalent)

    We compute percent_inr relative to grand total INR (0 -> empty list or 0 totals).
    """
    tid = trip_id if trip_id is not None else db.get_active_trip_id()
    rows = db.sums_by_currency(
        start_date=start_date, end_date=end_date, trip_id=tid
    )
    grand = sum(r["inr_total"] for r in rows) or 0.0
    if grand <= 0:
        return [
            CurrencyBreakdownItem(
                currency=r["currency"],
                amount_total=float(r["amount_total"]),
                inr_total=float(r["inr_total"]),
                percent_inr=0.0,
            )
            for r in rows
        ]
    return [
        CurrencyBreakdownItem(
            currency=r["currency"],
            amount_total=float(r["amount_total"]),
            inr_total=float(r["inr_total"]),
            percent_inr=round2(r["inr_total"] / grand * 100),
        )
        for r in rows
    ]


# ---------------- Category Breakdown (T08.05) -----------------
@dataclass(frozen=True)
class CategoryBreakdownItem:
    category: str
    inr_total: float
    percent: float


def compute_category_breakdown(
    db: Database,
    start_date: date | None = None,
    end_date: date | None = None,
    trip_id: int | None = None,
) -> list[CategoryBreakdownItem]:
    """Return list of category totals (already percent-enriched by DAL).

    DAL `sums_by_category` already returns rows with keys:
        - category
        - inr_total
        - percent (rounded to 2 decimals, sums ~100%)
    We simply wrap into immutable dataclasses for consistency with other analytics.
    """
    tid = trip_id if trip_id is not None else db.get_active_trip_id()
    rows = db.sums_by_category(
        start_date=start_date, end_date=end_date, trip_id=tid
    )
    return [
        CategoryBreakdownItem(
            category=r["category"],
            inr_total=float(r["inr_total"]),
            percent=float(r["percent"]),
        )
        for r in rows
    ]


# ---------------- Trend Data (T08.06) -----------------
@dataclass(frozen=True)
class TrendPoint:
    date: date
    daily_total_inr: float
    cumulative_total_inr: float


def compute_trend_data(
    db: Database,
    start_date: date | None = None,
    end_date: date | None = None,
    trip_id: int | None = None,
) -> list[TrendPoint]:
    """Return chronological list of daily totals plus cumulative INR spend.

    Source data from DAL `daily_totals` which already applies optional date
    filtering and returns rows ordered ASC by day. We then compute cumulative
    sum in order.

    If there are no expenses in the range returns empty list.
    """
    tid = trip_id if trip_id is not None else db.get_active_trip_id()
    rows = db.daily_totals(start_date=start_date, end_date=end_date, trip_id=tid)
    cumulative = 0.0
    points: list[TrendPoint] = []
    for r in rows:
        daily = float(r["total_inr"])
        cumulative += daily
        points.append(
            TrendPoint(
                date=r["day"],
                daily_total_inr=daily,
                cumulative_total_inr=round2(cumulative),
            )
        )
    return points
