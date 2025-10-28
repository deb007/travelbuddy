from __future__ import annotations
from datetime import date
from typing import Literal, Optional
from app.db.dal import Database
from app.core.config import get_settings
from app.services.trip_context import get_active_trip_id

Phase = Literal["pre-trip", "trip"]


def _get_db() -> Database:
    settings = get_settings()
    return Database(settings.db_path)


def get_trip_dates(db: Optional[Database] = None):
    db = db or _get_db()
    trip_id = get_active_trip_id(db)
    return db.get_trip_dates(trip_id=trip_id)


def resolve_phase(d: date, trip_dates: Optional[dict] = None) -> Phase:
    """Return 'pre-trip' if date is strictly before start_date, else 'trip'.

    If trip dates not yet configured, treat all as 'trip' (simpler for MVP).
    """
    if trip_dates is None:
        return "trip"
    start = trip_dates["start_date"]
    # end date isn't needed yet for classification but may be used later for post-trip logic
    if d < start:
        return "pre-trip"
    return "trip"
