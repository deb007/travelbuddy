from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional, List

from pydantic import BaseModel, root_validator, validator


class TripBase(BaseModel):
    name: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    currencies: Optional[List[str]] = None

    @validator("name")
    def _name_not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("name cannot be empty")
        return value.strip()

    @validator("end_date")
    def _end_not_before_start(cls, end: Optional[date], values: dict) -> Optional[date]:
        start: Optional[date] = values.get("start_date")
        if end and start and end < start:
            raise ValueError("end_date cannot be before start_date")
        return end

    @validator("currencies")
    def _valid_currencies(cls, currencies: Optional[List[str]]) -> Optional[List[str]]:
        if currencies is not None:
            if len(currencies) == 0:
                raise ValueError("currencies list cannot be empty")
            # Remove duplicates while preserving order
            seen = set()
            unique = []
            for cur in currencies:
                cur_upper = cur.upper().strip()
                if cur_upper and cur_upper not in seen:
                    seen.add(cur_upper)
                    unique.append(cur_upper)
            if len(unique) == 0:
                raise ValueError("currencies list cannot be empty")
            return unique
        return currencies


class TripCreate(TripBase):
    status: Literal["active", "archived"] = "active"
    make_active: bool = False


class TripUpdate(BaseModel):
    name: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[Literal["active", "archived"]] = None
    currencies: Optional[List[str]] = None

    @root_validator
    def _at_least_one(cls, values: dict) -> dict:
        if not any(
            values.get(field) is not None
            for field in ("name", "start_date", "end_date", "status", "currencies")
        ):
            raise ValueError("at least one field must be provided")
        return values

    @validator("name")
    def _name_not_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError("name cannot be empty")
        return value.strip() if value is not None else None

    @validator("end_date")
    def _end_not_before_start(cls, end: Optional[date], values: dict) -> Optional[date]:
        start: Optional[date] = values.get("start_date")
        if end and start and end < start:
            raise ValueError("end_date cannot be before start_date")
        return end

    @validator("currencies")
    def _valid_currencies(cls, currencies: Optional[List[str]]) -> Optional[List[str]]:
        if currencies is not None:
            if len(currencies) == 0:
                raise ValueError("currencies list cannot be empty")
            # Remove duplicates while preserving order
            seen = set()
            unique = []
            for cur in currencies:
                cur_upper = cur.upper().strip()
                if cur_upper and cur_upper not in seen:
                    seen.add(cur_upper)
                    unique.append(cur_upper)
            if len(unique) == 0:
                raise ValueError("currencies list cannot be empty")
            return unique
        return currencies


class TripOut(TripBase):
    id: int
    status: Literal["active", "archived"]
    currencies: List[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class TripResetRequest(BaseModel):
    preserve_settings: bool = True


class TripResetAllRequest(BaseModel):
    preserve_settings: bool = True
