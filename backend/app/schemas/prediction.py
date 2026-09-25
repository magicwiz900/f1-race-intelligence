from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.driver import DriverResponse


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
