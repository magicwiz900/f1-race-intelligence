import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession, joinedload

from app.api.deps import get_db
from app.models import Driver, Prediction, Race, Session as F1Session, SessionResult
from app.schemas.prediction import PredictionResponse, RacePredictionsResponse
from app.schemas.race import RaceResponse
from app.schemas.session import SessionResponse, SessionResultResponse
from app.schemas.track_geometry import TrackGeometryResponse
from app.schemas.sector_geometry import SectorGeometryResponse
from app.services.f1_data.track_geometry import TrackGeometryService, TrackGeometryUnavailableError
from app.services.f1_data.sector_geometry import SectorGeometryService, SectorGeometryUnavailableError
from app.services.prediction_service.predictor import PredictionService
from app.services.race_service import get_next_upcoming_race
from datetime import date

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/races", tags=["Races"])

VALID_PREDICTION_STAGES = {"PRE_FP1", "POST_FP1", "POST_FP2", "POST_FP3", "POST_QUALIFYING"}


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
    "/upcoming",
    response_model=RaceResponse,
    summary="Get next upcoming race",
    description="Retrieve details of the next chronologically upcoming race relative to today (or optional reference date).",
)
def get_upcoming_race(
    as_of_date: Optional[str] = Query(None, description="Optional reference date (YYYY-MM-DD)"),
    db: DBSession = Depends(get_db),
):
    ref_d = None
    if as_of_date:
        try:
            ref_d = date.fromisoformat(as_of_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format for as_of_date. Use YYYY-MM-DD.",
            )

    race = get_next_upcoming_race(db, as_of_date=ref_d)
    if not race:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No upcoming races found in calendar.",
        )
    return race


@router.get(
    "/upcoming/predictions",
    response_model=RacePredictionsResponse,
    summary="Get upcoming race predictions",
    description="Retrieve predictions for the next upcoming race in the calendar. Defaults to PRE_FP1 stage.",
)
def get_upcoming_race_predictions(
    stage: Optional[str] = Query("PRE_FP1", description="Filter by prediction stage (defaults to PRE_FP1)"),
    as_of_date: Optional[str] = Query(None, description="Optional reference date (YYYY-MM-DD)"),
    db: DBSession = Depends(get_db),
):
    ref_d = None
    if as_of_date:
        try:
            ref_d = date.fromisoformat(as_of_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format for as_of_date. Use YYYY-MM-DD.",
            )

    race = get_next_upcoming_race(db, as_of_date=ref_d)
    if not race:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No upcoming races found in calendar.",
        )

    return _get_race_predictions_impl(race.id, stage, db)


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


def _get_race_predictions_impl(race_id: int, stage: Optional[str], db: DBSession) -> RacePredictionsResponse:
    target_stage = (stage or "POST_QUALIFYING").upper()
    if target_stage not in VALID_PREDICTION_STAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid prediction stage '{stage}'. Supported predictive stages: PRE_FP1, POST_FP1, POST_FP2, POST_FP3, POST_QUALIFYING",
        )

    try:
        service = PredictionService(db)
        return service.predict_race_stage(race_id=race_id, stage=target_stage)
    except HTTPException:
        raise
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Race with ID {race_id} not found",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate race predictions: {str(e)}",
        )


@router.get(
    "/{race_id}/predictions",
    response_model=RacePredictionsResponse,
    summary="Get race predictions",
    description="Retrieve stage-aware model predictions for a race. Defaults to POST_QUALIFYING stage if omitted.",
)
def get_race_predictions(
    race_id: int,
    stage: Optional[str] = Query(
        None,
        description="Filter by prediction stage (e.g. PRE_FP1, POST_FP1, POST_FP2, POST_FP3, POST_QUALIFYING)",
    ),
    db: DBSession = Depends(get_db),
):
    return _get_race_predictions_impl(race_id, stage, db)


@router.get(
    "/{race_id}/predictions/{stage}",
    response_model=RacePredictionsResponse,
    summary="Get stage-specific race predictions",
    description="Retrieve stage-aware model predictions for a specific race-weekend stage.",
)
def get_race_predictions_by_stage(
    race_id: int,
    stage: str,
    db: DBSession = Depends(get_db),
):
    return _get_race_predictions_impl(race_id, stage, db)


@router.get(
    "/{race_id}/track-geometry",
    response_model=TrackGeometryResponse,
    summary="Get race track geometry",
    description="Retrieve normalized track geometry coordinates for a race circuit from FastF1 telemetry.",
)
def get_race_track_geometry(
    race_id: int,
    db: DBSession = Depends(get_db),
):
    race = db.get(Race, race_id)
    if not race:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Race with ID {race_id} not found",
        )

    try:
        service = TrackGeometryService()
        geometry_data = service.get_track_geometry(
            race_id=race.id,
            season=race.season,
            round_num=race.round,
            race_name=race.race_name,
            circuit=race.circuit,
        )
        return geometry_data
    except TrackGeometryUnavailableError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Track geometry telemetry unavailable for race ID {race_id}: {str(e)}",
        )
    except Exception as e:
        logger.exception("Failed to retrieve track geometry for race_id %d: %s", race_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve track geometry telemetry.",
        )


@router.get(
    "/{race_id}/sector-geometry",
    response_model=SectorGeometryResponse,
    summary="Get race sector geometry",
    description="Retrieve normalized sector-by-sector track geometry coordinates for a race circuit from FastF1 telemetry.",
)
def get_race_sector_geometry(
    race_id: int,
    db: DBSession = Depends(get_db),
):
    race = db.get(Race, race_id)
    if not race:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Race with ID {race_id} not found",
        )

    try:
        service = SectorGeometryService()
        geometry_data = service.get_sector_geometry(
            race_id=race.id,
            season=race.season,
            round_num=race.round,
            race_name=race.race_name,
            circuit=race.circuit,
        )
        return geometry_data
    except SectorGeometryUnavailableError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sector geometry telemetry unavailable for race ID {race_id}: {str(e)}",
        )
    except Exception as e:
        logger.exception("Failed to retrieve sector geometry for race_id %d: %s", race_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve sector geometry telemetry.",
        )


