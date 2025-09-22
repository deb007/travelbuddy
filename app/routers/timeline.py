from fastapi import APIRouter, Depends, HTTPException
from app.core.config import get_settings
from app.db.dal import Database
from app.models.timeline import TripDates

router = APIRouter(prefix="/trip-dates", tags=["timeline"])


def get_db() -> Database:
    settings = get_settings()
    return Database(settings.db_path)


@router.get("/", response_model=TripDates, summary="Get configured trip dates")
async def get_trip_dates_endpoint(db: Database = Depends(get_db)):
    data = db.get_trip_dates()
    if not data:
        raise HTTPException(status_code=404, detail="trip dates not set")
    return TripDates(**data)


@router.put("/", response_model=TripDates, summary="Set or update trip dates")
async def set_trip_dates_endpoint(payload: TripDates, db: Database = Depends(get_db)):
    try:
        db.set_trip_dates(start_date=payload.start_date, end_date=payload.end_date)
    except Exception as e:  # pragma: no cover
        raise HTTPException(
            status_code=500, detail="failed to persist trip dates"
        ) from e
    return payload
