import logging
from datetime import date
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from app.models import Race

logger = logging.getLogger(__name__)


def get_next_upcoming_race(db: DBSession, as_of_date: Optional[date] = None) -> Optional[Race]:
    """
    Retrieve the next upcoming F1 race chronologically relative to as_of_date (defaults to date.today()).
    Query: First race where Race.race_date >= as_of_date, ordered by race_date ASC, round ASC.
    """
    ref_date = as_of_date or date.today()
    stmt = (
        select(Race)
        .where(Race.race_date >= ref_date)
        .order_by(Race.race_date.asc(), Race.round.asc())
        .limit(1)
    )
    race = db.scalar(stmt)
    if race:
        logger.info("Found next upcoming race: ID %d (%s, %s)", race.id, race.race_name, race.race_date)
    else:
        logger.warning("No upcoming races found in database on or after date %s", ref_date)
    return race
