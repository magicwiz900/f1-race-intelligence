from datetime import date, datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Date, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.session import Session
    from app.models.prediction import Prediction


class Race(Base):
    __tablename__ = "races"
    __table_args__ = (
        UniqueConstraint("season", "round", name="uq_race_season_round"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    season: Mapped[int] = mapped_column(nullable=False)
    round: Mapped[int] = mapped_column(nullable=False)
    race_name: Mapped[str] = mapped_column(String(100), nullable=False)
    circuit: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    race_date: Mapped[date] = mapped_column(Date, nullable=False)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now(), nullable=False)

    sessions: Mapped[List["Session"]] = relationship(
        "Session",
        back_populates="race",
        cascade="all, delete-orphan",
    )
    predictions: Mapped[List["Prediction"]] = relationship(
        "Prediction",
        back_populates="race",
        cascade="all, delete-orphan",
    )
