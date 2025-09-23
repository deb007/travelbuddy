"""Data Access Layer utilities for MVP.

Scope (T02.04):
- Insert expense
- List expenses (basic filters: start_date, end_date, currency)
- Update budget spent (incremental) for same-currency expenses

Design choices:
- Lightweight wrapper class holding db_path
- Returns Pydantic models where appropriate (ExpenseOut) later; for now return dicts to keep coupling minimal (conversion utility included)
- Uses parameterized queries only
"""

from __future__ import annotations
from pathlib import Path
import sqlite3
from typing import List, Optional, Dict, Any
from datetime import date

from app.models import ExpenseIn
from app.models.constants import FOREX_CURRENCIES


class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # Expense CRUD -------------------------------------------------
    def insert_expense(
        self,
        expense: ExpenseIn,
        inr_equivalent: float,
        exchange_rate: float,
    ) -> int:
        """Insert a new expense and return its id."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO expenses (
                    amount, currency, category, description, date, payment_method,
                    inr_equivalent, exchange_rate
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
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
            return cur.lastrowid

    def insert_expense_with_budget(
        self,
        expense: ExpenseIn,
        inr_equivalent: float,
        exchange_rate: float,
    ) -> int:
        """Insert expense and increment matching budget spent atomically.

        Extended in T06.03: If payment_method == 'forex' and currency is a
        supported forex currency (SGD, MYR), also increment forex_cards
        spent_amount (creating row if missing). No balance enforcement yet
        (MVP keeps it simple; validation may be added later). Forex card
        loaded_amount is not changed here—only spent_amount accrues.
        """
        with self._connect() as conn:
            cur = conn.cursor()
            # 1. Ensure budget row exists (idempotent)
            cur.execute(
                "INSERT OR IGNORE INTO budgets (currency, max_amount, spent_amount) VALUES (?, 0, 0)",
                (expense.currency,),
            )
            # 2. Insert expense
            cur.execute(
                """
                INSERT INTO expenses (
                    amount, currency, category, description, date, payment_method,
                    inr_equivalent, exchange_rate
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
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
            expense_id = cur.lastrowid
            # 3. Increment spent
            cur.execute(
                "UPDATE budgets SET spent_amount = spent_amount + ?, updated_at = (strftime('%Y-%m-%dT%H:%M:%fZ','now')) WHERE currency = ?",
                (expense.amount, expense.currency),
            )
            # 4. (T06.03) If forex payment, increment forex card spent
            if (
                expense.payment_method == "forex"
                and expense.currency in FOREX_CURRENCIES
            ):
                cur.execute(
                    "INSERT OR IGNORE INTO forex_cards (currency, loaded_amount, spent_amount) VALUES (?, 0, 0)",
                    (expense.currency,),
                )
                cur.execute(
                    "UPDATE forex_cards SET spent_amount = spent_amount + ?, updated_at=(strftime('%Y-%m-%dT%H:%M:%fZ','now')) WHERE currency=?",
                    (expense.amount, expense.currency),
                )
            return expense_id

    def update_budget_delta(self, currency: str, delta: float) -> None:
        """Atomic update of the budget spent amount for a given currency."""
        with self._connect() as conn:
            cur = conn.cursor()
            # Ensure budget row exists
            cur.execute(
                "INSERT OR IGNORE INTO budgets (currency, max_amount, spent_amount) VALUES (?, 0, 0)",
                (currency,),
            )
            # Update the spent amount atomically
            cur.execute(
                "UPDATE budgets SET spent_amount = spent_amount + ?, updated_at = (strftime('%Y-%m-%dT%H:%M:%fZ','now')) WHERE currency = ?",
                (delta, currency),
            )

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
    ) -> None:
        """Update an expense and adjust budget spent atomically.

        budget_delta = new_amount - old_amount (original currency units). May be negative.
        Currency is assumed immutable at this stage (PATCH endpoint will enforce).
        """
        with self._connect() as conn:
            cur = conn.cursor()
            # Fetch existing state for forex delta logic
            cur.execute(
                "SELECT amount, currency, payment_method FROM expenses WHERE id=?",
                (expense_id,),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError("expense not found")
            currency = row["currency"]
            old_amount = float(row["amount"])
            old_pm = row["payment_method"]
            # Update expense
            cur.execute(
                """
                UPDATE expenses
                SET amount=?, category=?, description=?, date=?, payment_method=?,
                    inr_equivalent=?, exchange_rate=?, updated_at=(strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                WHERE id=?
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
            # Adjust budget spent (ensure row exists first)
            if abs(budget_delta) > 1e-9:
                cur.execute(
                    "INSERT OR IGNORE INTO budgets (currency, max_amount, spent_amount) VALUES (?, 0, 0)",
                    (currency,),
                )
                cur.execute(
                    "UPDATE budgets SET spent_amount = spent_amount + ?, updated_at=(strftime('%Y-%m-%dT%H:%M:%fZ','now')) WHERE currency=?",
                    (budget_delta, currency),
                )
            # (T06.03) Forex spent adjustments
            # Cases:
            # 1. old forex & new forex: adjust by delta (new_amount - old_amount)
            # 2. old forex & new non-forex: subtract old_amount
            # 3. old non-forex & new forex: add new_amount
            # 4. neither forex: no-op
            if currency in FOREX_CURRENCIES and (
                old_pm == "forex" or new_payment_method == "forex"
            ):
                cur.execute(
                    "INSERT OR IGNORE INTO forex_cards (currency, loaded_amount, spent_amount) VALUES (?, 0, 0)",
                    (currency,),
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
                        "UPDATE forex_cards SET spent_amount = MAX(0, spent_amount + ?), updated_at=(strftime('%Y-%m-%dT%H:%M:%fZ','now')) WHERE currency=?",
                        (forex_delta, currency),
                    )

    def delete_expense_with_budget(self, expense_id: int) -> None:
        """Delete an expense and decrement budget spent atomically.

        If the expense doesn't exist, raises ValueError. Spent amount is reduced
        by the expense's original amount but never clamped below zero explicitly;
        budgets table integrity (no negative spent) should be maintained by consumers
        logging valid data. For safety, we clamp at SQL level using MAX().
        """
        with self._connect() as conn:
            cur = conn.cursor()
            # Fetch amount & currency first
            cur.execute(
                "SELECT amount, currency, payment_method FROM expenses WHERE id=?",
                (expense_id,),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError("expense not found")
            amount = float(row["amount"])
            currency = row["currency"]
            payment_method = row["payment_method"]
            # Delete expense
            cur.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
            if cur.rowcount == 0:
                raise ValueError("expense not found")
            # Ensure budget row exists (defensive)
            cur.execute(
                "INSERT OR IGNORE INTO budgets (currency, max_amount, spent_amount) VALUES (?, 0, 0)",
                (currency,),
            )
            # Decrement spent but not below zero
            cur.execute(
                "UPDATE budgets SET spent_amount = MAX(0, spent_amount - ?), updated_at=(strftime('%Y-%m-%dT%H:%M:%fZ','now')) WHERE currency=?",
                (amount, currency),
            )
            # (T06.03) If deleted expense was forex, decrement forex card spent
            if payment_method == "forex" and currency in FOREX_CURRENCIES:
                cur.execute(
                    "INSERT OR IGNORE INTO forex_cards (currency, loaded_amount, spent_amount) VALUES (?, 0, 0)",
                    (currency,),
                )
                cur.execute(
                    "UPDATE forex_cards SET spent_amount = MAX(0, spent_amount - ?), updated_at=(strftime('%Y-%m-%dT%H:%M:%fZ','now')) WHERE currency=?",
                    (amount, currency),
                )

    def get_expense(self, expense_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM expenses WHERE id=?", (expense_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def list_expenses(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        currency: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List expenses with optional filters."""
        clauses = []
        params: List[Any] = []
        if start_date:
            clauses.append("date >= ?")
            params.append(start_date.isoformat())
        if end_date:
            clauses.append("date <= ?")
            params.append(end_date.isoformat())
        if currency:
            clauses.append("currency = ?")
            params.append(currency)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM expenses {where} ORDER BY date DESC, id DESC"
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    # Lightweight aggregation helpers (T08.02) ------------------
    def total_inr_spent(self) -> float:
        """Return total INR equivalent spent across all expenses (0.0 if none)."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT COALESCE(ROUND(SUM(inr_equivalent), 2), 0.0) FROM expenses"
            )
            val = cur.fetchone()[0]
            return float(val or 0.0)

    def earliest_expense_date(self) -> Optional[date]:
        """Return the earliest expense date or None if no expenses."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT MIN(date) FROM expenses")
            row = cur.fetchone()
            if not row or row[0] is None:
                return None
            return date.fromisoformat(row[0])

    # Budget helpers ------------------------------------------------
    def increment_budget_spent(self, currency: str, delta: float) -> None:
        """Increment spent_amount for a currency. Creates row if missing."""
        with self._connect() as conn:
            cur = conn.cursor()
            # Ensure row exists
            cur.execute(
                "INSERT OR IGNORE INTO budgets (currency, max_amount, spent_amount) VALUES (?, 0, 0)",
                (currency,),
            )
            cur.execute(
                "UPDATE budgets SET spent_amount = spent_amount + ?, updated_at = (strftime('%Y-%m-%dT%H:%M:%fZ','now')) WHERE currency = ?",
                (delta, currency),
            )

    def set_budget_max(self, currency: str, max_amount: float) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO budgets (currency, max_amount, spent_amount) VALUES (?, ?, 0) ON CONFLICT(currency) DO UPDATE SET max_amount=excluded.max_amount, updated_at=(strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
                (currency, max_amount),
            )

    def get_budget(self, currency: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM budgets WHERE currency=?", (currency,))
            row = cur.fetchone()
            return dict(row) if row else None

    def list_budgets(self) -> List[Dict[str, Any]]:
        """Return all budget rows ordered by currency."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM budgets ORDER BY currency")
            return [dict(r) for r in cur.fetchall()]

    # Aggregations -------------------------------------------------
    def daily_totals(
        self, start_date: Optional[date] = None, end_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """Return list of {date, total_inr} ordered ascending by date."""
        clauses = []
        params: List[Any] = []
        if start_date:
            clauses.append("date >= ?")
            params.append(start_date.isoformat())
        if end_date:
            clauses.append("date <= ?")
            params.append(end_date.isoformat())
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""
            SELECT date as day, ROUND(SUM(inr_equivalent), 2) as total_inr
            FROM expenses
            {where}
            GROUP BY date
            ORDER BY date ASC
        """
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def sums_by_currency(
        self, start_date: Optional[date] = None, end_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """Return total original amount & INR equivalent per currency."""
        clauses = []
        params: List[Any] = []
        if start_date:
            clauses.append("date >= ?")
            params.append(start_date.isoformat())
        if end_date:
            clauses.append("date <= ?")
            params.append(end_date.isoformat())
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""
            SELECT currency, ROUND(SUM(amount),2) as amount_total, ROUND(SUM(inr_equivalent),2) as inr_total
            FROM expenses
            {where}
            GROUP BY currency
            ORDER BY currency
        """
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def sums_by_category(
        self, start_date: Optional[date] = None, end_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """Return INR totals per category with percentage of grand total."""
        clauses = []
        params: List[Any] = []
        if start_date:
            clauses.append("date >= ?")
            params.append(start_date.isoformat())
        if end_date:
            clauses.append("date <= ?")
            params.append(end_date.isoformat())
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""
            SELECT category, ROUND(SUM(inr_equivalent),2) as inr_total
            FROM expenses
            {where}
            GROUP BY category
            ORDER BY inr_total DESC
        """
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            rows = cur.fetchall()
            totals = [dict(r) for r in rows]
            grand = sum(r["inr_total"] for r in totals) or 1.0
            for r in totals:
                r["percent"] = round((r["inr_total"] / grand) * 100, 2)
            return totals

    # Trip dates (timeline) ---------------------------------------
    def get_trip_dates(self) -> Optional[Dict[str, date]]:
        """Return stored trip start/end dates if both exist; else None.

        Values are stored in metadata table under keys:
          - trip_start_date
          - trip_end_date
        """
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT key, value FROM metadata WHERE key IN ('trip_start_date','trip_end_date')"
            )
            rows = cur.fetchall()
            if len(rows) < 2:
                return None
            data = {r["key"]: r["value"] for r in rows}
            if "trip_start_date" not in data or "trip_end_date" not in data:
                return None
            return {
                "start_date": date.fromisoformat(data["trip_start_date"]),
                "end_date": date.fromisoformat(data["trip_end_date"]),
            }

    def set_trip_dates(self, start_date: date, end_date: date) -> None:
        """Persist trip start & end dates atomically (upserts)."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO metadata(key,value) VALUES('trip_start_date',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=(strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
                (start_date.isoformat(),),
            )
            cur.execute(
                "INSERT INTO metadata(key,value) VALUES('trip_end_date',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=(strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
                (end_date.isoformat(),),
            )

    # Forex Cards -------------------------------------------------
    def get_forex_card(self, currency: str) -> Optional[Dict[str, Any]]:
        """Return forex card row for currency if exists (currency primary key)."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM forex_cards WHERE currency=?", (currency,))
            row = cur.fetchone()
            return dict(row) if row else None

    def list_forex_cards(self) -> List[Dict[str, Any]]:
        """Return all forex card rows ordered by currency."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM forex_cards ORDER BY currency")
            return [dict(r) for r in cur.fetchall()]

    def set_forex_card_loaded(self, currency: str, loaded_amount: float) -> None:
        """Upsert forex card loaded_amount keeping spent_amount intact.

        Creates row if missing (spent_amount=0). Rejects negative values.
        """
        if loaded_amount < 0:
            raise ValueError("loaded_amount cannot be negative")
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO forex_cards (currency, loaded_amount, spent_amount)
                VALUES (?, ?, 0)
                ON CONFLICT(currency) DO UPDATE SET
                  loaded_amount=excluded.loaded_amount,
                  updated_at=(strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                """,
                (currency, loaded_amount),
            )
