from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.session import Session
    from app.models.driver import Driver


class SessionResult(Base):
    __tablename__ = "session_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id", ondelete="CASCADE"), index=True, nullable=False)
    position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    lap_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sector_1: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sector_2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sector_3: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tyre: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    laps: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now(), nullable=False)

    session: Mapped["Session"] = relationship("Session", back_populates="session_results")
    driver: Mapped["Driver"] = relationship("Driver", back_populates="session_results")
