from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.driver import DriverResponse
from app.schemas.race import RaceResponse
from app.schemas.team import TeamResponse


class SessionResponse(BaseModel):
    id: int
    race_id: int
    session_type: str
    session_date: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SessionResultResponse(BaseModel):
    id: int
    session_id: int
    driver: DriverResponse
    team: Optional[TeamResponse] = None
    position: Optional[int] = None
    lap_time: Optional[float] = None
    sector_1: Optional[float] = None
    sector_2: Optional[float] = None
    sector_3: Optional[float] = None
    tyre: Optional[str] = None
    laps: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class SessionDetailResponse(SessionResponse):
    race: Optional[RaceResponse] = None
    session_results: List[SessionResultResponse] = []

    model_config = ConfigDict(from_attributes=True)
