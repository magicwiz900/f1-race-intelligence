from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession, joinedload

from app.api.deps import get_db
from app.models import Driver, Prediction, Race, Session as F1Session, SessionResult
from app.schemas.prediction import PredictionResponse
from app.schemas.race import RaceResponse
from app.schemas.session import SessionResponse, SessionResultResponse

router = APIRouter(prefix="/races", tags=["Races"])


@router.get(
    "",
    response_model=List[RaceResponse],
    summary="List F1 races",
    description="Retrieve a list of F1 races, ordered chronologically by season and round. Supports optional filtering by season and pagination.",
)
def list_races(
    season: Optional[int] = Query(None, description="Filter by season year (e.g. 2025)"),
    limit: int = Query(100, ge=1, le=500, description="Number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    db: DBSession = Depends(get_db),
):
    stmt = select(Race).order_by(Race.season.asc(), Race.round.asc())
    if season is not None:
        stmt = stmt.where(Race.season == season)
    
    stmt = stmt.offset(offset).limit(limit)
    races = db.scalars(stmt).all()
    return races


@router.get(
    "/{race_id}",
    response_model=RaceResponse,
    summary="Get single race",
    description="Retrieve details of a single race by its database ID.",
)
def get_race(
    race_id: int,
    db: DBSession = Depends(get_db),
):
    race = db.get(Race, race_id)
    if not race:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Race with ID {race_id} not found",
        )
    return race


@router.get(
    "/{race_id}/sessions",
    response_model=List[SessionResponse],
    summary="Get race sessions",
    description="Retrieve all sessions (FP1, FP2, FP3, QUALIFYING, RACE) associated with a given race.",
)
def get_race_sessions(
    race_id: int,
    db: DBSession = Depends(get_db),
):
    race = db.get(Race, race_id)
    if not race:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Race with ID {race_id} not found",
        )

    stmt = select(F1Session).where(F1Session.race_id == race_id).order_by(F1Session.id.asc())
    sessions = db.scalars(stmt).all()
    return sessions


@router.get(
    "/{race_id}/results",
    response_model=List[SessionResultResponse],
    summary="Get race session results",
    description="Retrieve session results for a race, with optional filtering by session_type (FP1, FP2, FP3, QUALIFYING, RACE).",
)
def get_race_results(
    race_id: int,
    session_type: Optional[str] = Query(
        None,
        description="Filter results by session type (e.g. FP1, FP2, FP3, QUALIFYING, RACE)",
    ),
    db: DBSession = Depends(get_db),
):
    race = db.get(Race, race_id)
    if not race:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Race with ID {race_id} not found",
        )

    stmt = (
        select(SessionResult)
        .join(SessionResult.session)
        .where(F1Session.race_id == race_id)
        .options(
            joinedload(SessionResult.driver).joinedload(Driver.team),
        )
    )

    if session_type:
        stmt = stmt.where(F1Session.session_type == session_type.upper())

    stmt = stmt.order_by(SessionResult.position.asc().nulls_last(), SessionResult.id.asc())
    results = db.scalars(stmt).all()
    
    # Structure results so driver team is accessible
    response_list = []
    for res in results:
        res_dict = {
            "id": res.id,
            "session_id": res.session_id,
            "driver": res.driver,
            "team": res.driver.team if res.driver else None,
            "position": res.position,
            "lap_time": res.lap_time,
            "sector_1": res.sector_1,
            "sector_2": res.sector_2,
            "sector_3": res.sector_3,
            "tyre": res.tyre,
            "laps": res.laps,
        }
        response_list.append(res_dict)

    return response_list


@router.get(
    "/{race_id}/predictions",
    response_model=List[PredictionResponse],
    summary="Get race predictions",
    description="Retrieve stage-aware model predictions for a race (e.g. PRE_FP1, POST_FP1, POST_FP2, POST_FP3, POST_QUALIFYING, FINAL). Returns empty list if no predictions exist.",
)
def get_race_predictions(
    race_id: int,
    stage: Optional[str] = Query(
        None,
        description="Filter by prediction stage (e.g. PRE_FP1, POST_FP1, POST_FP2, POST_FP3, POST_QUALIFYING, FINAL)",
    ),
    db: DBSession = Depends(get_db),
):
    race = db.get(Race, race_id)
    if not race:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Race with ID {race_id} not found",
        )

    stmt = (
        select(Prediction)
        .where(Prediction.race_id == race_id)
        .options(joinedload(Prediction.driver).joinedload(Driver.team))
    )

    if stage:
        stmt = stmt.where(Prediction.prediction_stage == stage.upper())

    stmt = stmt.order_by(Prediction.predicted_position.asc().nulls_last())
    predictions = db.scalars(stmt).all()
    return predictions
