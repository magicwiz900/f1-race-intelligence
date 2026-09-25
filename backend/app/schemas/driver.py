from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.team import TeamResponse


class DriverResponse(BaseModel):
    id: int
    driver_code: str
    name: str
    country: Optional[str] = None
    team: Optional[TeamResponse] = None

    model_config = ConfigDict(from_attributes=True)


class DriverSummaryResponse(BaseModel):
    id: int
    driver_code: str
    name: str
    country: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
