"""Domain-level expense validation utilities (T04.01).

This module is intentionally lightweight for MVP. Pydantic model validation
already enforces field-level rules (amount>0, enumerations, no future date) and
a cross-field constraint (forex payment method only for SGD/MYR) added in
`ExpenseIn` root validator.

Future enhancements (post-T04.01):
- Trip phase date range enforcement once trip start/end stored in metadata.
- Prevent editing currency of existing expenses (handled at route level).
- Additional category / payment method business constraints.

Usage: call `validate_expense_domain(expense_in)` prior to DAL insertion in
api route handlers. Currently returns the object unchanged but centralizes
hook point for future rules without scattering logic.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from app.models.expense import ExpenseIn


def validate_expense_domain(expense: "ExpenseIn") -> "ExpenseIn":
    """Perform domain-level validations beyond Pydantic field checks.

    Currently a no-op placeholder returning the expense. This keeps route
    code prepared for future additions (e.g., trip date boundaries once
    implemented in timeline tasks T05.*).
    """
    # Placeholder: no extra checks yet for MVP scope of T04.01
    return expense
