from __future__ import annotations
from pydantic import BaseModel, validator, Field
from .constants import FOREX_CURRENCIES


class ForexCard(BaseModel):
    currency: str
    loaded_amount: float = Field(0, ge=0)
    spent_amount: float = Field(0, ge=0)

    @validator("currency")
    def valid_currency(cls, v: str) -> str:
        if v not in FOREX_CURRENCIES:
            raise ValueError("unsupported forex currency")
        return v

    @property
    def remaining(self) -> float:
        return max(self.loaded_amount - self.spent_amount, 0)

    def low_balance_flag(self) -> bool:
        if self.loaded_amount <= 0:
            return False
        return (self.remaining / self.loaded_amount) < 0.20
