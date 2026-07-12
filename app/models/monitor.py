from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import MonitorMethod, MonitorStatus

if TYPE_CHECKING:
    from app.models.check_job import CheckJob
    from app.models.incident import Incident
    from app.models.user import User


class Monitor(Base):
    __tablename__ = "monitors"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    target_url: Mapped[str] = mapped_column(String(2048))
    method: Mapped[MonitorMethod] = mapped_column(
        Enum(MonitorMethod, name="monitor_method"),
        default=MonitorMethod.GET,
        server_default=MonitorMethod.GET.value,
    )
    check_interval_seconds: Mapped[int] = mapped_column(Integer)
    consecutive_failure_threshold: Mapped[int] = mapped_column(
        Integer,
        default=2,
        server_default="2",
    )
    status: Mapped[MonitorStatus] = mapped_column(
        Enum(MonitorStatus, name="monitor_status"),
        default=MonitorStatus.active,
        server_default=MonitorStatus.active.value,
    )
    consecutive_failures: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped["User"] = relationship(back_populates="monitors")
    check_jobs: Mapped[list["CheckJob"]] = relationship(
        back_populates="monitor",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    incidents: Mapped[list["Incident"]] = relationship(
        back_populates="monitor",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
