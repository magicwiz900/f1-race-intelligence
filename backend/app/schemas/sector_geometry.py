from typing import List
from pydantic import BaseModel, ConfigDict
from app.schemas.track_geometry import TrackPoint


class SectorData(BaseModel):
    sector: int
    start_distance: float
    end_distance: float
    start_relative_distance: float
    end_relative_distance: float
    points: List[TrackPoint]

    model_config = ConfigDict(from_attributes=True)


class SectorGeometryResponse(BaseModel):
    race_id: int
    season: int
    race_name: str
    circuit: str
    source: str = "FastF1 telemetry"
    session_type: str
    coordinate_system: str = "normalized"
    total_distance: float
    sectors: List[SectorData]

    model_config = ConfigDict(from_attributes=True)
