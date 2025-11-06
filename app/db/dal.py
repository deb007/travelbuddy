"""Data Access Layer utilities with multi-trip support.

Responsibilities
----------------
- Provide CRUD helpers for trips and track the active trip context.
- Scope budgets, expenses, and forex card operations to a specific trip,
  defaulting to the active trip when callers omit an explicit identifier.
- Offer aggregation helpers (totals, breakdowns) that respect trip isolation.
"""

from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional
from datetime import date

from app.models import ExpenseIn
from app.models.constants import FOREX_CURRENCIES
from app.services import app_settings

UTC_NOW_SQL = "strftime('%Y-%m-%dT%H:%M:%fZ','now')"
VALID_TRIP_STATUSES = {"active", "archived"}
_UNSET = object()


class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    # ------------------------------------------------------------------
    # Connection helpers
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _resolve_trip_id(
        self, trip_id: Optional[int], cur: Optional[sqlite3.Cursor] = None
    ) -> int:
        """Return provided trip_id or fall back to active trip (creates metadata when missing)."""
        if trip_id is not None:
            return trip_id
        if cur is None:
            with self._connect() as conn:
                trip_id = self._resolve_trip_id(None, conn.cursor())
                conn.commit()
                return trip_id

        cur.execute("SELECT value FROM metadata WHERE key = 'active_trip_id'")
        row = cur.fetchone()
        if row:
            try:
                return int(row[0])
            except (TypeError, ValueError):
                pass  # fall back to trips table

        # Prefer most recently updated active trip; fall back to earliest trip.
        cur.execute(
            """
            SELECT id FROM trips
            WHERE status = 'active'
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """
        )
        row = cur.fetchone()
        if not row:
            cur.execute("SELECT id FROM trips ORDER BY id LIMIT 1")
            row = cur.fetchone()
        if not row:
            raise RuntimeError("No trips configured; cannot resolve active trip id")
        resolved = int(row[0])
        cur.execute(
            f"""
            INSERT INTO metadata (key, value)
            VALUES ('active_trip_id', ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = ({UTC_NOW_SQL})
            """,
            (str(resolved),),
        )
        return resolved

    # ------------------------------------------------------------------
    # Trip CRUD & context utilities
    def list_trips(self, include_archived: bool = True) -> List[Dict[str, Any]]:
        query = "SELECT * FROM trips"
        params: List[Any] = []
        if not include_archived:
            query += " WHERE status != 'archived'"
        query += " ORDER BY created_at ASC"
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]

    def get_trip(self, trip_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM trips WHERE id = ?", (trip_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def get_active_trip(self) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            cur = conn.cursor()
            trip_id = self._resolve_trip_id(None, cur)
            cur.execute("SELECT * FROM trips WHERE id = ?", (trip_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def get_active_trip_id(self) -> int:
        with self._connect() as conn:
            return self._resolve_trip_id(None, conn.cursor())

    def create_trip(
        self,
        name: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        status: str = "active",
        make_active: bool = False,
    ) -> int:
        if status not in VALID_TRIP_STATUSES:
            raise ValueError(f"Unsupported trip status '{status}'")
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                INSERT INTO trips (name, start_date, end_date, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ({UTC_NOW_SQL}), ({UTC_NOW_SQL}))
                """,
                (
                    name,
                    start_date.isoformat() if start_date else None,
                    end_date.isoformat() if end_date else None,
                    status,
                ),
            )
            trip_id = int(cur.lastrowid)
            if make_active or status == "active":
                self._set_active_trip(cur, trip_id)
            conn.commit()
            return trip_id

    def get_expense(
        self, expense_id: int, trip_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            cur = conn.cursor()
            tid = self._resolve_trip_id(trip_id, cur)
            cur.execute(
                "SELECT * FROM expenses WHERE id = ? AND trip_id = ?",
                (expense_id, tid),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def list_expenses(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        currency: Optional[str] = None,
        trip_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        clauses = ["trip_id = ?"]
        params: List[Any] = []
        with self._connect() as conn:
            cur = conn.cursor()
            tid = self._resolve_trip_id(trip_id, cur)
            params.append(tid)
            if start_date:
                clauses.append("date >= ?")
                params.append(start_date.isoformat())
            if end_date:
                clauses.append("date <= ?")
                params.append(end_date.isoformat())
            if currency:
                clauses.append("currency = ?")
                params.append(currency)
            where = " WHERE " + " AND ".join(clauses)
            sql = f"SELECT * FROM expenses{where} ORDER BY date DESC, id DESC"
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def count_expenses(self, trip_id: Optional[int] = None) -> int:
        with self._connect() as conn:
            cur = conn.cursor()
            tid = self._resolve_trip_id(trip_id, cur)
            cur.execute("SELECT COUNT(*) FROM expenses WHERE trip_id = ?", (tid,))
            row = cur.fetchone()
            return int(row[0] if row and row[0] is not None else 0)

    # ------------------------------------------------------------------
    # Aggregations (trip scoped)
    def total_inr_spent(self, trip_id: Optional[int] = None) -> float:
        with self._connect() as conn:
            cur = conn.cursor()
            tid = self._resolve_trip_id(trip_id, cur)
            cur.execute(
                "SELECT COALESCE(ROUND(SUM(inr_equivalent), 2), 0.0) FROM expenses WHERE trip_id = ?",
                (tid,),
            )
            val = cur.fetchone()[0]
            return float(val or 0.0)

    def earliest_expense_date(self, trip_id: Optional[int] = None) -> Optional[date]:
        with self._connect() as conn:
            cur = conn.cursor()
            tid = self._resolve_trip_id(trip_id, cur)
            cur.execute("SELECT MIN(date) FROM expenses WHERE trip_id = ?", (tid,))
            row = cur.fetchone()
            if not row or row[0] is None:
                return None
            return date.fromisoformat(row[0])

    def daily_totals(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        trip_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        clauses = ["trip_id = ?"]
        params: List[Any] = []
        with self._connect() as conn:
            cur = conn.cursor()
            tid = self._resolve_trip_id(trip_id, cur)
            params.append(tid)
            if start_date:
                clauses.append("date >= ?")
                params.append(start_date.isoformat())
            if end_date:
                clauses.append("date <= ?")
                params.append(end_date.isoformat())
            where = " WHERE " + " AND ".join(clauses)
            sql = f"""
                SELECT date as day, ROUND(SUM(inr_equivalent), 2) as total_inr
                FROM expenses
                {where}
                GROUP BY date
                ORDER BY date ASC
            """
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def sums_by_currency(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        trip_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        clauses = ["trip_id = ?"]
        params: List[Any] = []
        with self._connect() as conn:
            cur = conn.cursor()
            tid = self._resolve_trip_id(trip_id, cur)
            params.append(tid)
            if start_date:
                clauses.append("date >= ?")
                params.append(start_date.isoformat())
            if end_date:
                clauses.append("date <= ?")
                params.append(end_date.isoformat())
            where = " WHERE " + " AND ".join(clauses)
            sql = f"""
                SELECT currency,
                       ROUND(SUM(amount), 2) as amount_total,
                       ROUND(SUM(inr_equivalent), 2) as inr_total
                FROM expenses
                {where}
                GROUP BY currency
                ORDER BY currency
            """
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def sums_by_category(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        trip_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        clauses = ["trip_id = ?"]
        params: List[Any] = []
        with self._connect() as conn:
            cur = conn.cursor()
            tid = self._resolve_trip_id(trip_id, cur)
            params.append(tid)
            if start_date:
                clauses.append("date >= ?")
                params.append(start_date.isoformat())
            if end_date:
                clauses.append("date <= ?")
                params.append(end_date.isoformat())
            where = " WHERE " + " AND ".join(clauses)
            sql = f"""
                SELECT category, ROUND(SUM(inr_equivalent), 2) as inr_total
                FROM expenses
                {where}
                GROUP BY category
                ORDER BY inr_total DESC
            """
            cur.execute(sql, params)
            rows = cur.fetchall()
            totals = [dict(r) for r in rows]
            grand = sum(r["inr_total"] for r in totals) or 1.0
            for r in totals:
                r["percent"] = round((r["inr_total"] / grand) * 100, 2)
            return totals

    # ------------------------------------------------------------------
    # Budget helpers (trip scoped)
    def increment_budget_spent(
        self, currency: str, delta: float, trip_id: Optional[int] = None
    ) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            tid = self._resolve_trip_id(trip_id, cur)
            cur.execute(
                """
                INSERT OR IGNORE INTO budgets (trip_id, currency, max_amount, spent_amount, updated_at)
                VALUES (?, ?, 0, 0, ({utc_now}))
                """.format(utc_now=UTC_NOW_SQL),
                (tid, currency),
            )
            cur.execute(
                """
                UPDATE budgets
                SET spent_amount = spent_amount + ?, updated_at = ({utc_now})
                WHERE trip_id = ? AND currency = ?
                """.format(utc_now=UTC_NOW_SQL),
                (delta, tid, currency),
            )
            conn.commit()

    def set_budget_max(
        self, currency: str, max_amount: float, trip_id: Optional[int] = None
    ) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            tid = self._resolve_trip_id(trip_id, cur)
            cur.execute(
                """
                INSERT INTO budgets (trip_id, currency, max_amount, spent_amount, updated_at)
                VALUES (?, ?, ?, 0, ({utc_now}))
                ON CONFLICT(trip_id, currency) DO UPDATE SET
                    max_amount = excluded.max_amount,
                    updated_at = ({utc_now})
                """.format(utc_now=UTC_NOW_SQL),
                (tid, currency, max_amount),
            )
            conn.commit()

    def get_budget(
        self, currency: str, trip_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            cur = conn.cursor()
            tid = self._resolve_trip_id(trip_id, cur)
            cur.execute(
                "SELECT * FROM budgets WHERE trip_id = ? AND currency = ?",
                (tid, currency),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def list_budgets(self, trip_id: Optional[int] = None) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            cur = conn.cursor()
            tid = self._resolve_trip_id(trip_id, cur)
            cur.execute(
                "SELECT * FROM budgets WHERE trip_id = ? ORDER BY currency",
                (tid,),
            )
            return [dict(r) for r in cur.fetchall()]

    # ------------------------------------------------------------------
    # Trip dates convenience (mapped onto trips table)
    def get_trip_dates(
        self, trip_id: Optional[int] = None
    ) -> Optional[Dict[str, date]]:
        with self._connect() as conn:
            cur = conn.cursor()
            tid = self._resolve_trip_id(trip_id, cur)
            cur.execute(
                "SELECT start_date, end_date FROM trips WHERE id = ?",
                (tid,),
            )
            row = cur.fetchone()
            if not row:
                return None
            start_raw, end_raw = row["start_date"], row["end_date"]
            if not start_raw or not end_raw:
                return None
            return {
                "start_date": date.fromisoformat(start_raw),
                "end_date": date.fromisoformat(end_raw),
            }

    def set_trip_dates(
        self, start_date: date, end_date: date, trip_id: Optional[int] = None
    ) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            tid = self._resolve_trip_id(trip_id, cur)
            cur.execute(
                f"""
                UPDATE trips
                SET start_date = ?, end_date = ?, updated_at = ({UTC_NOW_SQL})
                WHERE id = ?
                """,
                (start_date.isoformat(), end_date.isoformat(), tid),
            )
            if cur.rowcount == 0:
                raise ValueError("Trip not found")
            conn.commit()

    # ------------------------------------------------------------------
    # Forex card helpers (trip scoped)
    def get_forex_card(
        self, currency: str, trip_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            cur = conn.cursor()
            tid = self._resolve_trip_id(trip_id, cur)
            cur.execute(
                "SELECT * FROM forex_cards WHERE trip_id = ? AND currency = ?",
                (tid, currency),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def list_forex_cards(self, trip_id: Optional[int] = None) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            cur = conn.cursor()
            tid = self._resolve_trip_id(trip_id, cur)
            cur.execute(
                "SELECT * FROM forex_cards WHERE trip_id = ? ORDER BY currency",
                (tid,),
            )
            return [dict(r) for r in cur.fetchall()]

    def set_forex_card_loaded(
        self, currency: str, loaded_amount: float, trip_id: Optional[int] = None
    ) -> None:
        if loaded_amount < 0:
            raise ValueError("loaded_amount cannot be negative")
        with self._connect() as conn:
            cur = conn.cursor()
            tid = self._resolve_trip_id(trip_id, cur)
            cur.execute(
                """
                INSERT INTO forex_cards (trip_id, currency, loaded_amount, spent_amount, updated_at)
                VALUES (?, ?, ?, 0, ({utc_now}))
                ON CONFLICT(trip_id, currency) DO UPDATE SET
                    loaded_amount = excluded.loaded_amount,
                    updated_at = ({utc_now})
                """.format(utc_now=UTC_NOW_SQL),
                (tid, currency, loaded_amount),
            )
            conn.commit()

            return trip_id

    def update_trip(
        self,
        trip_id: int,
        *,
        name: Any = _UNSET,
        start_date: Any = _UNSET,
        end_date: Any = _UNSET,
        status: Any = _UNSET,
    ) -> None:
        updates: List[str] = []
        params: List[Any] = []

        if name is not _UNSET:
            updates.append("name = ?")
            params.append(name)
        if start_date is not _UNSET:
            iso_val = start_date.isoformat() if isinstance(start_date, date) else None
            updates.append("start_date = ?")
            params.append(iso_val)
        if end_date is not _UNSET:
            iso_val = end_date.isoformat() if isinstance(end_date, date) else None
            updates.append("end_date = ?")
            params.append(iso_val)
        if status is not _UNSET:
            if status not in VALID_TRIP_STATUSES:
                raise ValueError(f"Unsupported trip status '{status}'")
            updates.append("status = ?")
            params.append(status)

        if not updates:
            return

        updates.append(f"updated_at = ({UTC_NOW_SQL})")
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                f"UPDATE trips SET {', '.join(updates)} WHERE id = ?",
                (*params, trip_id),
            )
            if cur.rowcount == 0:
                raise ValueError("Trip not found")
            conn.commit()

    def set_active_trip(self, trip_id: int) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            self._set_active_trip(cur, trip_id)
            conn.commit()

    def _set_active_trip(self, cur: sqlite3.Cursor, trip_id: int) -> None:
        cur.execute("SELECT status FROM trips WHERE id = ?", (trip_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError("Trip not found")
        status = row["status"]
        if status == "archived":
            raise ValueError(
                "Cannot activate an archived trip. Please unarchive it first."
            )

        cur.execute(
            f"UPDATE trips SET updated_at = ({UTC_NOW_SQL}) WHERE id = ?",
            (trip_id,),
        )
        cur.execute(
            f"""
            INSERT INTO metadata (key, value)
            VALUES ('active_trip_id', ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = ({UTC_NOW_SQL})
            """,
            (str(trip_id),),
        )

    def unarchive_trip(self, trip_id: int, make_active: bool = False) -> None:
        """Explicitly unarchive a trip and optionally make it active.

        Args:
            trip_id: The ID of the trip to unarchive
            make_active: If True, also set this trip as the active trip

        Raises:
            ValueError: If trip not found or trip is not archived
        """
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT status FROM trips WHERE id = ?", (trip_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError("Trip not found")
            if row["status"] != "archived":
                raise ValueError("Trip is not archived")

            cur.execute(
                f"UPDATE trips SET status = 'active', updated_at = ({UTC_NOW_SQL}) WHERE id = ?",
                (trip_id,),
            )

            if make_active:
                self._set_active_trip(cur, trip_id)

            conn.commit()

    # ------------------------------------------------------------------
    # Expense CRUD
    def insert_expense(
        self,
        expense: ExpenseIn,
        inr_equivalent: float,
        exchange_rate: float,
        trip_id: Optional[int] = None,
    ) -> int:
        with self._connect() as conn:
            cur = conn.cursor()
            tid = self._resolve_trip_id(trip_id, cur)
            cur.execute(
                f"""
                INSERT INTO expenses (
                    trip_id, amount, currency, category, description, date, payment_method,
                    inr_equivalent, exchange_rate, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ({UTC_NOW_SQL}), ({UTC_NOW_SQL}))
                """,
                (
                    tid,
                    expense.amount,
                    expense.currency,
                    expense.category,
                    expense.description,
                    expense.date.isoformat(),
                    expense.payment_method,
                    inr_equivalent,
                    exchange_rate,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)

    def insert_expense_with_budget(
        self,
        expense: ExpenseIn,
        inr_equivalent: float,
        exchange_rate: float,
        trip_id: Optional[int] = None,
    ) -> int:
        with self._connect() as conn:
            cur = conn.cursor()
            tid = self._resolve_trip_id(trip_id, cur)

            # Budget existence / auto-create / defaults
            if app_settings.get_budget_auto_create(self):
                defaults = app_settings.get_default_budget_amounts(self)
                default_max = float(defaults.get(expense.currency.upper(), 0.0))
                cur.execute(
                    """
                    INSERT OR IGNORE INTO budgets (trip_id, currency, max_amount, spent_amount, updated_at)
                    VALUES (?, ?, ?, 0, ({utc_now}))
                    """.format(utc_now=UTC_NOW_SQL),
                    (tid, expense.currency, default_max),
                )
            else:
                cur.execute(
                    "SELECT max_amount, spent_amount FROM budgets WHERE trip_id = ? AND currency = ?",
                    (tid, expense.currency),
                )
                if cur.fetchone() is None:
                    raise ValueError("Budget row missing and auto-create disabled")

            if app_settings.get_budget_enforce_cap(self):
                cur.execute(
                    "SELECT max_amount, spent_amount FROM budgets WHERE trip_id = ? AND currency = ?",
                    (tid, expense.currency),
                )
                brow = cur.fetchone()
                if brow is not None:
                    max_amt = float(brow[0] or 0)
                    spent_amt = float(brow[1] or 0)
                    if max_amt > 0 and (spent_amt + expense.amount) > max_amt + 1e-9:
                        raise ValueError("Budget cap exceeded")

            # Insert expense row
            cur.execute(
                f"""
                INSERT INTO expenses (
                    trip_id, amount, currency, category, description, date, payment_method,
                    inr_equivalent, exchange_rate, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ({UTC_NOW_SQL}), ({UTC_NOW_SQL}))
                """,
                (
                    tid,
                    expense.amount,
                    expense.currency,
                    expense.category,
                    expense.description,
                    expense.date.isoformat(),
                    expense.payment_method,
                    inr_equivalent,
                    exchange_rate,
                ),
            )
            expense_id = int(cur.lastrowid)

            # Increment budget spent
            cur.execute(
                """
                UPDATE budgets
                SET spent_amount = spent_amount + ?, updated_at = ({utc_now})
                WHERE trip_id = ? AND currency = ?
                """.format(utc_now=UTC_NOW_SQL),
                (expense.amount, tid, expense.currency),
            )

            # Forex spent tracking
            if (
                expense.payment_method == "forex"
                and expense.currency in FOREX_CURRENCIES
            ):
                cur.execute(
                    """
                    INSERT OR IGNORE INTO forex_cards (trip_id, currency, loaded_amount, spent_amount, updated_at)
                    VALUES (?, ?, 0, 0, ({utc_now}))
                    """.format(utc_now=UTC_NOW_SQL),
                    (tid, expense.currency),
                )
                cur.execute(
                    """
                    UPDATE forex_cards
                    SET spent_amount = spent_amount + ?, updated_at = ({utc_now})
                    WHERE trip_id = ? AND currency = ?
                    """.format(utc_now=UTC_NOW_SQL),
                    (expense.amount, tid, expense.currency),
                )

            conn.commit()
            return expense_id

    def update_budget_delta(
        self, currency: str, delta: float, trip_id: Optional[int] = None
    ) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            tid = self._resolve_trip_id(trip_id, cur)
            cur.execute(
                """
                INSERT OR IGNORE INTO budgets (trip_id, currency, max_amount, spent_amount, updated_at)
                VALUES (?, ?, 0, 0, ({utc_now}))
                """.format(utc_now=UTC_NOW_SQL),
                (tid, currency),
            )
            cur.execute(
                """
                UPDATE budgets
                SET spent_amount = spent_amount + ?, updated_at = ({utc_now})
                WHERE trip_id = ? AND currency = ?
                """.format(utc_now=UTC_NOW_SQL),
                (delta, tid, currency),
            )
            conn.commit()

    def update_expense_with_budget(
        self,
        expense_id: int,
        new_amount: float,
        new_category: str,
        new_description: Optional[str],
        new_date: date,
        new_payment_method: str,
        new_inr_equivalent: float,
        new_exchange_rate: float,
        budget_delta: float,
        trip_id: Optional[int] = None,
    ) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT amount, currency, payment_method, trip_id FROM expenses WHERE id = ?",
                (expense_id,),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError("expense not found")
            tid = int(row["trip_id"])
            if trip_id is not None and trip_id != tid:
                raise ValueError("expense does not belong to provided trip")
            currency = row["currency"]
            old_amount = float(row["amount"])
            old_pm = row["payment_method"]

            if app_settings.get_budget_enforce_cap(self) and budget_delta > 0:
                cur.execute(
                    "SELECT max_amount, spent_amount FROM budgets WHERE trip_id = ? AND currency = ?",
                    (tid, currency),
                )
                brow = cur.fetchone()
                if brow is not None:
                    max_amt = float(brow[0] or 0)
                    spent_amt = float(brow[1] or 0)
                    if max_amt > 0 and (spent_amt + budget_delta) > max_amt + 1e-9:
                        raise ValueError("Budget cap exceeded")

            cur.execute(
                f"""
                UPDATE expenses
                SET amount = ?, category = ?, description = ?, date = ?, payment_method = ?,
                    inr_equivalent = ?, exchange_rate = ?, updated_at = ({UTC_NOW_SQL})
                WHERE id = ?
                """,
                (
                    new_amount,
                    new_category,
                    new_description,
                    new_date.isoformat(),
                    new_payment_method,
                    new_inr_equivalent,
                    new_exchange_rate,
                    expense_id,
                ),
            )
            if cur.rowcount == 0:
                raise ValueError("expense not found")

            if abs(budget_delta) > 1e-9:
                cur.execute(
                    """
                    INSERT OR IGNORE INTO budgets (trip_id, currency, max_amount, spent_amount, updated_at)
                    VALUES (?, ?, 0, 0, ({utc_now}))
                    """.format(utc_now=UTC_NOW_SQL),
                    (tid, currency),
                )
                cur.execute(
                    """
                    UPDATE budgets
                    SET spent_amount = spent_amount + ?, updated_at = ({utc_now})
                    WHERE trip_id = ? AND currency = ?
                    """.format(utc_now=UTC_NOW_SQL),
                    (budget_delta, tid, currency),
                )

            if currency in FOREX_CURRENCIES and (
                old_pm == "forex" or new_payment_method == "forex"
            ):
                cur.execute(
                    """
                    INSERT OR IGNORE INTO forex_cards (trip_id, currency, loaded_amount, spent_amount, updated_at)
                    VALUES (?, ?, 0, 0, ({utc_now}))
                    """.format(utc_now=UTC_NOW_SQL),
                    (tid, currency),
                )
                if old_pm == "forex" and new_payment_method == "forex":
                    forex_delta = new_amount - old_amount
                elif old_pm == "forex" and new_payment_method != "forex":
                    forex_delta = -old_amount
                elif old_pm != "forex" and new_payment_method == "forex":
                    forex_delta = new_amount
                else:
                    forex_delta = 0.0
                if abs(forex_delta) > 1e-9:
                    cur.execute(
                        """
                        UPDATE forex_cards
                        SET spent_amount = MAX(0, spent_amount + ?), updated_at = ({utc_now})
                        WHERE trip_id = ? AND currency = ?
                        """.format(utc_now=UTC_NOW_SQL),
                        (forex_delta, tid, currency),
                    )

            conn.commit()

    def delete_expense_with_budget(
        self, expense_id: int, trip_id: Optional[int] = None
    ) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT amount, currency, payment_method, trip_id FROM expenses WHERE id = ?",
                (expense_id,),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError("expense not found")
            amount = float(row["amount"])
            currency = row["currency"]
            payment_method = row["payment_method"]
            tid = int(row["trip_id"])
            if trip_id is not None and trip_id != tid:
                raise ValueError("expense does not belong to provided trip")

            cur.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
            if cur.rowcount == 0:
                raise ValueError("expense not found")

            cur.execute(
                """
                INSERT OR IGNORE INTO budgets (trip_id, currency, max_amount, spent_amount, updated_at)
                VALUES (?, ?, 0, 0, ({utc_now}))
                """.format(utc_now=UTC_NOW_SQL),
                (tid, currency),
            )
            cur.execute(
                """
                UPDATE budgets
                SET spent_amount = MAX(0, spent_amount - ?), updated_at = ({utc_now})
                WHERE trip_id = ? AND currency = ?
                """.format(utc_now=UTC_NOW_SQL),
                (amount, tid, currency),
            )

            if payment_method == "forex" and currency in FOREX_CURRENCIES:
                cur.execute(
                    """
                    INSERT OR IGNORE INTO forex_cards (trip_id, currency, loaded_amount, spent_amount, updated_at)
                    VALUES (?, ?, 0, 0, ({utc_now}))
                    """.format(utc_now=UTC_NOW_SQL),
                    (tid, currency),
                )
                cur.execute(
                    """
                    UPDATE forex_cards
                    SET spent_amount = MAX(0, spent_amount - ?), updated_at = ({utc_now})
                    WHERE trip_id = ? AND currency = ?
                    """.format(utc_now=UTC_NOW_SQL),
                    (amount, tid, currency),
                )

            conn.commit()


__all__ = ["Database"]
