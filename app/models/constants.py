"""Domain constants and enumerations for validation.

MVP keeps these lightweight; could evolve to Enum classes if needed.
"""

from typing import Set

CURRENCIES: Set[str] = {"INR", "SGD", "MYR"}
FOREX_CURRENCIES: Set[str] = {"SGD", "MYR"}
PAYMENT_METHODS: Set[str] = {"cash", "forex", "card"}
CATEGORIES: Set[str] = {
    # Core spending
    "food",
    "transport",
    "accommodation",
    "activities",
    "shopping",
    # Pre-trip & misc per PRD (visa/fees, insurance, forex, SIM, other)
    "visa_fees",
    "insurance",
    "forex",
    "sim",
    "other",
    # Legacy placeholder kept for backward compatibility with earlier seed data
    "misc",
}
