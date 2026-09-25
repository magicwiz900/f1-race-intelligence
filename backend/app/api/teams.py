from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession, selectinload

from app.api.deps import get_db
from app.models import Team
from app.schemas.team import TeamDetailResponse, TeamResponse

router = APIRouter(prefix="/teams", tags=["Teams"])


@router.get(
    "",
    response_model=List[TeamResponse],
    summary="List F1 teams/constructors",
    description="Retrieve a list of F1 constructor teams.",
)
def list_teams(
    db: DBSession = Depends(get_db),
):
    stmt = select(Team).order_by(Team.name.asc())
    teams = db.scalars(stmt).all()
    return teams


@router.get(
    "/{team_id}",
    response_model=TeamDetailResponse,
    summary="Get single team",
    description="Retrieve details of a single team by database ID, including its associated drivers.",
)
def get_team(
    team_id: int,
    db: DBSession = Depends(get_db),
):
    stmt = select(Team).options(selectinload(Team.drivers)).where(Team.id == team_id)
    team = db.scalar(stmt)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team with ID {team_id} not found",
        )
    return team
