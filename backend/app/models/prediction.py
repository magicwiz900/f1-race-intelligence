from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.race import Race
    from app.models.driver import Driver


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id", ondelete="CASCADE"), index=True, nullable=False)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id", ondelete="CASCADE"), index=True, nullable=False)
    prediction_stage: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    predicted_position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    win_probability: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    podium_probability: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    top5_probability: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    race: Mapped["Race"] = relationship("Race", back_populates="predictions")
    driver: Mapped["Driver"] = relationship("Driver", back_populates="predictions")
