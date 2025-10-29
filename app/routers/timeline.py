from fastapi import APIRouter, Depends, HTTPException

from app.core.config import get_settings
from app.db.dal import Database
from app.models.timeline import TripDates

router = APIRouter(prefix="/trips/{trip_id}/dates", tags=["timeline"])


def get_db() -> Database:
    settings = get_settings()
    return Database(settings.db_path)


@router.get("/", response_model=TripDates, summary="Get configured trip dates for a trip")
async def get_trip_dates_endpoint(trip_id: int, db: Database = Depends(get_db)):
    data = db.get_trip_dates(trip_id=trip_id)
    if not data:
        raise HTTPException(status_code=404, detail="trip dates not set")
    return TripDates(**data)


@router.put("/", response_model=TripDates, summary="Set or update trip dates for a trip")
async def set_trip_dates_endpoint(
    trip_id: int, payload: TripDates, db: Database = Depends(get_db)
):
    try:
        db.set_trip_dates(
            start_date=payload.start_date, end_date=payload.end_date, trip_id=trip_id
        )
    except Exception as e:  # pragma: no cover
        raise HTTPException(
            status_code=500, detail="failed to persist trip dates"
        ) from e
    return payload
