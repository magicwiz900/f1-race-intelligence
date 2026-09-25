from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession, joinedload

from app.api.deps import get_db
from app.models import Driver, Race, Session as F1Session, SessionResult
from app.schemas.driver import DriverResponse

router = APIRouter(prefix="/drivers", tags=["Drivers"])


@router.get(
    "",
    response_model=List[DriverResponse],
    summary="List F1 drivers",
    description="Retrieve a list of drivers, optionally filtered by season year.",
)
def list_drivers(
    season: Optional[int] = Query(None, description="Filter drivers by season year (e.g. 2025)"),
    db: DBSession = Depends(get_db),
):
    stmt = select(Driver).options(joinedload(Driver.team))

    if season is not None:
        stmt = (
            stmt.join(SessionResult, SessionResult.driver_id == Driver.id)
            .join(F1Session, F1Session.id == SessionResult.session_id)
            .join(Race, Race.id == F1Session.race_id)
            .where(Race.season == season)
            .distinct()
        )

    stmt = stmt.order_by(Driver.name.asc())
    drivers = db.scalars(stmt).all()
    return drivers


@router.get(
    "/{driver_id}",
    response_model=DriverResponse,
    summary="Get single driver",
    description="Retrieve details of a single driver by database ID, including associated team details.",
)
def get_driver(
    driver_id: int,
    db: DBSession = Depends(get_db),
):
    stmt = select(Driver).options(joinedload(Driver.team)).where(Driver.id == driver_id)
    driver = db.scalar(stmt)
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Driver with ID {driver_id} not found",
        )
    return driver
