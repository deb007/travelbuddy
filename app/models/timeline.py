from __future__ import annotations
from pydantic import BaseModel, validator
from datetime import date
from typing import Optional


class TripDates(BaseModel):
    start_date: date
    end_date: date

    @validator("end_date")
    def end_not_before_start(cls, v: date, values):  # type: ignore[override]
        sd: Optional[date] = values.get("start_date")
        if sd and v < sd:
            raise ValueError("end_date cannot be before start_date")
        return v
