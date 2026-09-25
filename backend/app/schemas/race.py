from datetime import date
from typing import Optional
from pydantic import BaseModel, ConfigDict


class RaceResponse(BaseModel):
    id: int
    season: int
    round: int
    race_name: str
    circuit: str
    country: Optional[str] = None
    race_date: date

    model_config = ConfigDict(from_attributes=True)
