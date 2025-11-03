from __future__ import annotations

from datetime import date, datetime
import json

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from app.core.config import get_settings
from app.db.dal import Database
from app.models.trip import (
    TripCreate,
    TripUpdate,
    TripOut,
    TripResetRequest,
    TripResetAllRequest,
)
from app.models.timeline import TripDates
from app.services.trip_context import clear_trip_context
from app.services.reset_utils import reset_trip_data

router = APIRouter(prefix="/trips", tags=["trips"])


def get_db() -> Database:
    settings = get_settings()
    return Database(settings.db_path)


def _row_to_trip(row: dict) -> TripOut:
    start_raw = row.get("start_date")
    end_raw = row.get("end_date")
    created_raw = row.get("created_at")
    updated_raw = row.get("updated_at")
    currencies_raw = row.get("currencies")

    # Parse currencies from JSON
    try:
        currencies = (
            json.loads(currencies_raw) if currencies_raw else ["INR", "SGD", "MYR"]
        )
    except (json.JSONDecodeError, TypeError):
        currencies = ["INR", "SGD", "MYR"]

    return TripOut(
        id=int(row["id"]),
        name=row["name"],
        start_date=date.fromisoformat(start_raw) if start_raw else None,
        end_date=date.fromisoformat(end_raw) if end_raw else None,
        status=row["status"],
        currencies=currencies,
        created_at=datetime.fromisoformat(created_raw.replace("Z", ""))
        if isinstance(created_raw, str)
        else created_raw,
        updated_at=datetime.fromisoformat(updated_raw.replace("Z", ""))
        if isinstance(updated_raw, str)
        else updated_raw,
    )


@router.get("/", response_model=list[TripOut], summary="List trips")
async def list_trips(
    include_archived: bool = Query(
        True, description="Include trips with status 'archived' in results"
    ),
    db: Database = Depends(get_db),
):
    rows = db.list_trips(include_archived=include_archived)
    return [_row_to_trip(r) for r in rows]


@router.post(
    "/",
    response_model=TripOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create trip",
)
async def create_trip(payload: TripCreate, db: Database = Depends(get_db)):
    if payload.make_active and payload.status == "archived":
        raise HTTPException(
            status_code=400, detail="cannot set make_active when status=archived"
        )
    try:
        trip_id = db.create_trip(
            name=payload.name,
            start_date=payload.start_date,
            end_date=payload.end_date,
            status=payload.status,
            make_active=payload.make_active,
            currencies=payload.currencies,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    row = db.get_trip(trip_id)
    if not row:
        raise HTTPException(status_code=500, detail="trip not found after creation")
    if payload.make_active or payload.status == "active":
        clear_trip_context()
    return _row_to_trip(row)


@router.get(
    "/{trip_id}",
    response_model=TripOut,
    summary="Get trip details",
)
async def get_trip(trip_id: int, db: Database = Depends(get_db)):
    row = db.get_trip(trip_id)
    if not row:
        raise HTTPException(status_code=404, detail="trip not found")
    return _row_to_trip(row)


@router.patch(
    "/{trip_id}",
    response_model=TripOut,
    summary="Update trip metadata",
)
async def update_trip(
    trip_id: int, payload: TripUpdate, db: Database = Depends(get_db)
):
    updates: dict[str, object] = {}
    if payload.name is not None:
        updates["name"] = payload.name
    if payload.start_date is not None:
        updates["start_date"] = payload.start_date
    if payload.end_date is not None:
        updates["end_date"] = payload.end_date
    if payload.status is not None:
        updates["status"] = payload.status
    if payload.currencies is not None:
        updates["currencies"] = payload.currencies
    try:
        db.update_trip(trip_id, **updates)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    row = db.get_trip(trip_id)
    if not row:
        raise HTTPException(status_code=404, detail="trip not found")
    if payload.status is not None:
        clear_trip_context()
    return _row_to_trip(row)


@router.post(
    "/{trip_id}/activate",
    response_model=TripOut,
    summary="Set active trip",
)
async def activate_trip(trip_id: int, db: Database = Depends(get_db)):
    try:
        db.set_active_trip(trip_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="trip not found")
    clear_trip_context()
    row = db.get_trip(trip_id)
    if not row:
        raise HTTPException(status_code=404, detail="trip not found")
    return _row_to_trip(row)


@router.post(
    "/{trip_id}/archive",
    response_model=TripOut,
    summary="Archive trip",
)
async def archive_trip(trip_id: int, db: Database = Depends(get_db)):
    try:
        db.update_trip(trip_id, status="archived")
    except ValueError:
        raise HTTPException(status_code=404, detail="trip not found")
    clear_trip_context()
    row = db.get_trip(trip_id)
    if not row:
        raise HTTPException(status_code=404, detail="trip not found")
    return _row_to_trip(row)


@router.post(
    "/{trip_id}/reset",
    response_model=TripOut,
    summary="Reset trip data",
)
async def reset_trip(
    trip_id: int,
    payload: TripResetRequest = Body(default=TripResetRequest()),
    db: Database = Depends(get_db),
):
    row = db.get_trip(trip_id)
    if not row:
        raise HTTPException(status_code=404, detail="trip not found")
    try:
        reset_trip_data(
            db,
            preserve_settings=payload.preserve_settings,
            trip_id=trip_id,
            wipe_all=False,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail="failed to reset trip") from exc
    clear_trip_context()
    row = db.get_trip(trip_id)
    if not row:
        raise HTTPException(status_code=404, detail="trip not found after reset")
    return _row_to_trip(row)


@router.post(
    "/reset-all",
    response_model=TripOut,
    summary="Wipe all trips and data",
)
async def reset_all_trips(
    payload: TripResetAllRequest = Body(default=TripResetAllRequest()),
    db: Database = Depends(get_db),
):
    try:
        reset_trip_data(
            db,
            preserve_settings=payload.preserve_settings,
            trip_id=None,
            wipe_all=True,
        )
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=500, detail="failed to reset all trips"
        ) from exc
    clear_trip_context()
    row = db.get_active_trip()
    if not row:
        raise HTTPException(status_code=500, detail="no active trip after reset")
    return _row_to_trip(row)


@router.get(
    "/{trip_id}/dates",
    response_model=TripDates,
    summary="Get trip date range",
)
async def get_trip_dates(trip_id: int, db: Database = Depends(get_db)):
    data = db.get_trip_dates(trip_id=trip_id)
    if not data:
        raise HTTPException(status_code=404, detail="trip dates not set")
    return TripDates(**data)


@router.put(
    "/{trip_id}/dates",
    response_model=TripDates,
    summary="Set trip date range",
)
async def set_trip_dates(
    trip_id: int, payload: TripDates, db: Database = Depends(get_db)
):
    try:
        db.set_trip_dates(
            start_date=payload.start_date, end_date=payload.end_date, trip_id=trip_id
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail="failed to persist trip dates"
        ) from exc
    clear_trip_context()
    return payload
