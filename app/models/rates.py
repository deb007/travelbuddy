from __future__ import annotations
from pydantic import BaseModel, validator, Field
from datetime import datetime
from .constants import CURRENCIES


class RateRecord(BaseModel):
    base_currency: str
    quote_currency: str
    rate: float = Field(..., gt=0)
    fetched_at: datetime

    @validator("base_currency", "quote_currency")
    def valid_currency(cls, v: str) -> str:
        if v not in CURRENCIES:
            raise ValueError("unsupported currency")
        return v

    @validator("quote_currency")
    def not_same(cls, v: str, values):  # type: ignore[override]
        if "base_currency" in values and values["base_currency"] == v:
            raise ValueError("quote cannot equal base")
        return v
