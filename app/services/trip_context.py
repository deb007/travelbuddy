"""Trip context utilities to coordinate active-trip resolution.

Provides lightweight helpers that cache the active trip within a request
context while still delegating persistence duties to the data layer.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Dict, Optional

from app.core.config import get_settings
from app.db.dal import Database

_trip_id_ctx: ContextVar[Optional[int]] = ContextVar("trip_ctx_trip_id", default=None)
_trip_ctx: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    "trip_ctx_trip_record", default=None
)


def _get_db(db: Optional[Database]) -> Database:
    if db is not None:
        return db
    settings = get_settings()
    return Database(settings.db_path)


def get_active_trip_id(db: Optional[Database] = None) -> int:
    cached = _trip_id_ctx.get()
    if cached is not None:
        return cached
    database = _get_db(db)
    trip_id = database.get_active_trip_id()
    _trip_id_ctx.set(trip_id)
    return trip_id


def get_active_trip(db: Optional[Database] = None) -> Dict[str, Any]:
    cached = _trip_ctx.get()
    if cached is not None:
        return cached
    database = _get_db(db)
    trip = database.get_active_trip()
    if trip is None:
        raise RuntimeError("No active trip configured")
    _trip_ctx.set(trip)
    _trip_id_ctx.set(int(trip["id"]))
    return trip


def set_active_trip(trip_id: int, db: Optional[Database] = None) -> None:
    database = _get_db(db)
    database.set_active_trip(trip_id)
    _trip_id_ctx.set(trip_id)
    _trip_ctx.set(database.get_trip(trip_id))


def clear_trip_context() -> None:
    _trip_id_ctx.set(None)
    _trip_ctx.set(None)


__all__ = [
    "get_active_trip_id",
    "get_active_trip",
    "set_active_trip",
    "clear_trip_context",
]
