from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Task(Base):
    """A raw, unscheduled (or scheduled) item the user wants to do.

    Canonical fields per the thesis outline: difficulty, urgency, estimated
    time, and an optional category.
    """

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    title: Mapped[str] = mapped_column(String(200))
    difficulty: Mapped[int] = mapped_column(default=3)  # 1 (easy) - 5 (hard)
    urgency: Mapped[int] = mapped_column(default=3)  # 1 (low) - 5 (high)
    estimated_minutes: Mapped[int] = mapped_column(default=30)
    category: Mapped[str | None] = mapped_column(String(60), nullable=True)

    # pending -> scheduled -> done ; scheduling can also bounce back to pending
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    scheduled_events: Mapped[list["ScheduledEvent"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )
