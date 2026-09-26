from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession, joinedload

from app.api.deps import get_db
from app.models import Driver, Prediction
from app.schemas.prediction import PredictionResponse

router = APIRouter(prefix="/predictions", tags=["Predictions"])

SUPPORTED_PREDICTION_STAGES = [
    "PRE_FP1",
    "POST_FP1",
    "POST_FP2",
    "POST_FP3",
    "POST_QUALIFYING",
]


@router.get(
    "",
    response_model=List[PredictionResponse],
    summary="List predictions",
    description="Retrieve model predictions with optional filtering by race_id and prediction_stage. Returns an empty list if no predictions exist yet.",
)
def list_predictions(
    race_id: Optional[int] = Query(None, description="Filter predictions by race ID"),
    stage: Optional[str] = Query(
        None,
        description="Filter by stage: PRE_FP1, POST_FP1, POST_FP2, POST_FP3, POST_QUALIFYING, FINAL",
    ),
    db: DBSession = Depends(get_db),
):
    stmt = select(Prediction).options(joinedload(Prediction.driver).joinedload(Driver.team))

    if race_id is not None:
        stmt = stmt.where(Prediction.race_id == race_id)
    if stage:
        stmt = stmt.where(Prediction.prediction_stage == stage.upper())

    stmt = stmt.order_by(Prediction.predicted_position.asc().nulls_last(), Prediction.id.asc())
    predictions = db.scalars(stmt).all()
    return predictions


@router.get(
    "/stages",
    response_model=List[str],
    summary="List prediction stages",
    description="Get list of supported race-weekend prediction stages.",
)
def list_prediction_stages():
    return SUPPORTED_PREDICTION_STAGES
