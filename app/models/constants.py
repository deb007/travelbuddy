"""Domain constants and enumerations for validation.

MVP keeps these lightweight; could evolve to Enum classes if needed.
"""

from typing import Set

CURRENCIES: Set[str] = {"INR", "SGD", "MYR"}
FOREX_CURRENCIES: Set[str] = {"SGD", "MYR"}
PAYMENT_METHODS: Set[str] = {"cash", "forex", "card"}
CATEGORIES: Set[str] = {
    "food",
    "transport",
    "accommodation",
    "activities",
    "shopping",
    "misc",
}
