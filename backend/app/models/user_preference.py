from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserPreference(Base):
    """Per-user scheduling preferences.

    Supersedes the fixed scheduler constants on `Settings`, which now only
    supply the values a freshly created row is seeded with.
    """

    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)

    # Bounds of the schedulable day and how far ahead the solver plans.
    work_start_hour: Mapped[int] = mapped_column(default=8)
    work_end_hour: Mapped[int] = mapped_column(default=22)
    horizon_days: Mapped[int] = mapped_column(default=7)
    slot_minutes: Mapped[int] = mapped_column(default=15)

    # Window the user reports being sharpest in; harder tasks are pulled here.
    peak_focus_start_hour: Mapped[int] = mapped_column(default=9)
    peak_focus_end_hour: Mapped[int] = mapped_column(default=12)

    # The only two settings that can make a day less dense rather than more
    # tightly packed.
    min_break_minutes: Mapped[int] = mapped_column(default=0)
    max_daily_task_minutes: Mapped[int] = mapped_column(default=8 * 60)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Warsaw")

    preferred_categories: Mapped[list[str]] = mapped_column(JSON, default=list)
    disliked_categories: Mapped[list[str]] = mapped_column(JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
