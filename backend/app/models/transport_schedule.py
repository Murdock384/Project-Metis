"""Persistence for transport intent and its selected, refreshable route."""

from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TransportSchedule(Base):
    """Stable transport intent plus the currently selected route plan."""

    __tablename__ = "transport_schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    scheduled_event_id: Mapped[int] = mapped_column(
        ForeignKey("scheduled_events.id"), unique=True, index=True
    )
    target_event_id: Mapped[int | None] = mapped_column(
        ForeignKey("scheduled_events.id"), nullable=True, index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    provider: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="planned")
    transport_mode: Mapped[str] = mapped_column(String(20), default="transit")

    origin_json: Mapped[dict] = mapped_column(JSON)
    destination_json: Mapped[dict] = mapped_column(JSON)
    requested_arrival_time: Mapped[datetime]
    destination_buffer_minutes: Mapped[int] = mapped_column(default=5)
    safety_buffer_minutes: Mapped[int] = mapped_column(default=10)

    current_revision: Mapped[int] = mapped_column(default=1)
    generated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    valid_until: Mapped[datetime | None] = mapped_column(nullable=True)
    route_departure_time: Mapped[datetime]
    safe_leave_time: Mapped[datetime]
    estimated_arrival_time: Mapped[datetime]
    duration_minutes: Mapped[int]
    distance_meters: Mapped[int | None] = mapped_column(nullable=True)
    transfer_count: Mapped[int] = mapped_column(default=0)
    summary: Mapped[str] = mapped_column(String(1000))
    navigation_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    route_steps_json: Mapped[list] = mapped_column(JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    scheduled_event: Mapped["ScheduledEvent"] = relationship(
        "ScheduledEvent", foreign_keys=[scheduled_event_id], back_populates="transport_schedule"
    )
    revisions: Mapped[list["TransportRouteRevision"]] = relationship(
        back_populates="transport_schedule", cascade="all, delete-orphan"
    )


class TransportRouteRevision(Base):
    """Immutable audit trail of plans selected for one transport event."""

    __tablename__ = "transport_route_revisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    transport_schedule_id: Mapped[int] = mapped_column(ForeignKey("transport_schedules.id"), index=True)
    revision: Mapped[int]
    refresh_reason: Mapped[str] = mapped_column(String(30), default="initial")
    generated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    route_departure_time: Mapped[datetime]
    safe_leave_time: Mapped[datetime]
    estimated_arrival_time: Mapped[datetime]
    summary: Mapped[str] = mapped_column(String(1000))
    route_steps_json: Mapped[list] = mapped_column(JSON, default=list)
    selected: Mapped[bool] = mapped_column(default=True)

    transport_schedule: Mapped["TransportSchedule"] = relationship(back_populates="revisions")
