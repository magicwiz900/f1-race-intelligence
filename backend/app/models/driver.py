from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.team import Team
    from app.models.session_result import SessionResult
    from app.models.prediction import Prediction


class Driver(Base):
    __tablename__ = "drivers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    driver_code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    team_id: Mapped[Optional[int]] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now(), nullable=False)

    team: Mapped[Optional["Team"]] = relationship("Team", back_populates="drivers")
    session_results: Mapped[List["SessionResult"]] = relationship(
        "SessionResult",
        back_populates="driver",
        cascade="all, delete-orphan",
    )
    predictions: Mapped[List["Prediction"]] = relationship(
        "Prediction",
        back_populates="driver",
        cascade="all, delete-orphan",
    )
