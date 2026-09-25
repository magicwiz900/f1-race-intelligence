from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.driver import Driver


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    constructor_code: Mapped[Optional[str]] = mapped_column(String(50), unique=True, nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now(), nullable=False)

    drivers: Mapped[List["Driver"]] = relationship(
        "Driver",
        back_populates="team",
        cascade="all, delete-orphan",
    )
