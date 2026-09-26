from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.driver import DriverResponse


class PredictionItemResponse(BaseModel):
    driver_id: int
    driver_code: str
    driver_name: str
    team_id: Optional[int] = None
    team_name: Optional[str] = None
    raw_win_probability: float = Field(..., ge=0.0, le=1.0)
    race_share_probability: float = Field(..., ge=0.0, le=1.0)
    podium_probability: float = Field(..., ge=0.0, le=1.0)
    top5_probability: float = Field(..., ge=0.0, le=1.0)
    predicted_finish_position: float = Field(..., ge=1.0, le=20.0)

    model_config = ConfigDict(from_attributes=True)


class DataAvailabilitySchema(BaseModel):
    historical_form: bool
    fp1: bool
    fp2: bool
    fp3: bool
    qualifying: bool


class RacePredictionsResponse(BaseModel):
    race_id: int
    season: int
    round: int
    race_name: str
    stage: str
    predictions: List[PredictionItemResponse]
    data_availability: Optional[DataAvailabilitySchema] = None

    model_config = ConfigDict(from_attributes=True)


class PredictionResponse(BaseModel):
    id: int
    race_id: int
    driver_id: int
    driver: Optional[DriverResponse] = None
    prediction_stage: str
    predicted_position: Optional[int] = None
    win_probability: Optional[float] = None
    podium_probability: Optional[float] = None
    top5_probability: Optional[float] = None
    model_version: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
