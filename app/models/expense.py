from __future__ import annotations
from pydantic import BaseModel, validator, Field
from typing import Optional
from datetime import date, datetime
from .constants import CURRENCIES, PAYMENT_METHODS, CATEGORIES


class ExpenseIn(BaseModel):
    amount: float = Field(..., gt=0)
    currency: str
    category: str
    description: Optional[str] = None
    date: date
    payment_method: str

    @validator("currency")
    def valid_currency(cls, v: str) -> str:
        if v not in CURRENCIES:
            raise ValueError("unsupported currency")
        return v

    @validator("category")
    def valid_category(cls, v: str) -> str:
        if v not in CATEGORIES:
            raise ValueError("unsupported category")
        return v

    @validator("payment_method")
    def valid_payment_method(cls, v: str) -> str:
        if v not in PAYMENT_METHODS:
            raise ValueError("unsupported payment method")
        return v

    @validator("date")
    def date_not_future(cls, v: date) -> date:
        today = date.today()
        if v > today:
            raise ValueError("date cannot be in the future")
        return v


class ExpenseOut(ExpenseIn):
    id: int
    inr_equivalent: float
    exchange_rate: float
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
