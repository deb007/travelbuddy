from __future__ import annotations
from pydantic import BaseModel, validator, Field
from .constants import CURRENCIES


class Budget(BaseModel):
    currency: str
    max_amount: float = Field(..., ge=0)
    spent_amount: float = Field(0, ge=0)

    @validator("currency")
    def valid_currency(cls, v: str) -> str:
        if v not in CURRENCIES:
            raise ValueError("unsupported currency")
        return v

    @property
    def remaining(self) -> float:
        return max(self.max_amount - self.spent_amount, 0)

    def threshold_flags(self) -> dict:
        if self.max_amount <= 0:
            return {"eighty": False, "ninety": False}
        pct = (self.spent_amount / self.max_amount) * 100
        return {"eighty": pct >= 80, "ninety": pct >= 90}
