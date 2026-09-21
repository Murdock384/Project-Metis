from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ScheduledEvent(Base):
    """Canonical calendar entry. This table (NOT any external calendar
    service) is the source of truth the mobile calendar UI renders from.

    `calendar_event_id` is kept nullable now so a future Google Calendar
    adapter can attach an external event id without a schema change.
    """

    __tablename__ = "scheduled_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Transport entries are calendar events without a corresponding task.
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"), index=True, nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    # "task", "manual", or "transport".  `source` says who placed it;
    # event_type says what it represents.
    event_type: Mapped[str] = mapped_column(String(20), default="task")
    title: Mapped[str] = mapped_column(String(200))

    start_time: Mapped[datetime] = mapped_column(index=True)
    end_time: Mapped[datetime]

    # "scheduler" (placed by the OR-Tools engine) or "manual" (user drag/edit/quick-add)
    source: Mapped[str] = mapped_column(String(20), default="scheduler")

    calendar_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    task: Mapped["Task"] = relationship(back_populates="scheduled_events")
    transport_schedule: Mapped["TransportSchedule | None"] = relationship(
        back_populates="scheduled_event",
        cascade="all, delete-orphan",
        uselist=False,
        foreign_keys="TransportSchedule.scheduled_event_id",
    )
