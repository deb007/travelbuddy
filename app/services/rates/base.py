from __future__ import annotations

"""Rate provider abstraction (T07.01).

Defines a minimal interface so future tasks (T07.02-T07.05) can plug in
HTTP fetching, caching, overrides, etc.
"""
from abc import ABC, abstractmethod
from typing import Protocol


class RateProvider(ABC):
    base_currency: str = "INR"

    @abstractmethod
    def get_rate(self, quote_currency: str) -> float:
        """Return INR per 1 unit of quote_currency."""
        raise NotImplementedError


class SupportsCompute(Protocol):
    def compute_inr(self, amount: float, currency: str) -> float: ...
