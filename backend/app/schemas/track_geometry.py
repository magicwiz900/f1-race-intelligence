from typing import List
from pydantic import BaseModel, ConfigDict


class TrackPoint(BaseModel):
    x: float
    y: float

    model_config = ConfigDict(from_attributes=True)


class TrackGeometryResponse(BaseModel):
    race_id: int
    season: int
    race_name: str
    circuit: str
    source: str = "FastF1 telemetry"
    session_type: str
    coordinate_system: str = "normalized"
    point_count: int
    points: List[TrackPoint]

    model_config = ConfigDict(from_attributes=True)
