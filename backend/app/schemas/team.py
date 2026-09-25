from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class TeamResponse(BaseModel):
    id: int
    name: str
    constructor_code: Optional[str] = None
    country: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DriverSummaryForTeam(BaseModel):
    id: int
    driver_code: str
    name: str
    country: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TeamDetailResponse(TeamResponse):
    drivers: List[DriverSummaryForTeam] = []

    model_config = ConfigDict(from_attributes=True)
