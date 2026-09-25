from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession, joinedload, selectinload

from app.api.deps import get_db
from app.models import Driver, Session as F1Session, SessionResult
from app.schemas.session import SessionDetailResponse

router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.get(
    "/{session_id}",
    response_model=SessionDetailResponse,
    summary="Get single session",
    description="Retrieve detailed session information including race context and associated driver session results.",
)
def get_session(
    session_id: int,
    db: DBSession = Depends(get_db),
):
    stmt = (
        select(F1Session)
        .options(
            joinedload(F1Session.race),
            selectinload(F1Session.session_results)
            .joinedload(SessionResult.driver)
            .joinedload(Driver.team),
        )
        .where(F1Session.id == session_id)
    )
    session_obj = db.scalar(stmt)
    if not session_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with ID {session_id} not found",
        )

    # Format response object
    formatted_results = []
    for res in session_obj.session_results:
        res_dict = {
            "id": res.id,
            "session_id": res.session_id,
            "driver": res.driver,
            "team": res.driver.team if res.driver else None,
            "position": res.position,
            "lap_time": res.lap_time,
            "sector_1": res.sector_1,
            "sector_2": res.sector_2,
            "sector_3": res.sector_3,
            "tyre": res.tyre,
            "laps": res.laps,
        }
        formatted_results.append(res_dict)

    return {
        "id": session_obj.id,
        "race_id": session_obj.race_id,
        "session_type": session_obj.session_type,
        "session_date": session_obj.session_date,
        "race": session_obj.race,
        "session_results": formatted_results,
    }
