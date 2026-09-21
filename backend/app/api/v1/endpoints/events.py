from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import get_db
from app.models.scheduled_event import ScheduledEvent
from app.models.task import Task
from app.schemas.event import EventCreate, EventRead, EventUpdate

router = APIRouter(prefix="/events", tags=["events"])


def _to_event_read(event: ScheduledEvent, task: Task | None = None) -> EventRead:
    def display_time(value: datetime) -> datetime:
        # SQLite does not round-trip timezone metadata. Transport timestamps
        # are written in UTC, so restore that metadata for the public API.
        if event.event_type == "transport" and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

    return EventRead(
        id=event.id,
        task_id=event.task_id,
        task_title=task.title if task else None,
        title=event.title,
        event_type=event.event_type,
        category=task.category if task else None,
        start_time=display_time(event.start_time),
        end_time=display_time(event.end_time),
        source=event.source,
        calendar_event_id=event.calendar_event_id,
    )


@router.get("", response_model=list[EventRead])
def list_events(
    start: datetime | None = None,
    end: datetime | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(ScheduledEvent).where(ScheduledEvent.user_id == settings.dev_user_id)
    if start:
        stmt = stmt.where(ScheduledEvent.end_time >= start)
    if end:
        stmt = stmt.where(ScheduledEvent.start_time <= end)
    stmt = stmt.order_by(ScheduledEvent.start_time)
    events = db.scalars(stmt).all()
    return [_to_event_read(e, e.task) for e in events]


@router.post("", response_model=EventRead, status_code=201)
def create_event(payload: EventCreate, db: Session = Depends(get_db)):
    """Manual quick-add: either attach to an existing task, or create a
    brand-new ad-hoc task inline."""
    if payload.task_id is not None:
        task = db.get(Task, payload.task_id)
        if task is None or task.user_id != settings.dev_user_id:
            raise HTTPException(status_code=404, detail="Task not found")
    else:
        estimated_minutes = int((payload.end_time - payload.start_time).total_seconds() // 60)
        task = Task(
            user_id=settings.dev_user_id,
            title=payload.title,
            difficulty=payload.difficulty,
            urgency=payload.urgency,
            estimated_minutes=max(1, estimated_minutes),
            category=payload.category,
            status="scheduled",
        )
        db.add(task)
        db.flush()

    event = ScheduledEvent(
        task_id=task.id,
        user_id=settings.dev_user_id,
        title=task.title,
        event_type="manual",
        start_time=payload.start_time,
        end_time=payload.end_time,
        source="manual",
    )
    task.status = "scheduled"
    db.add(event)
    db.commit()
    db.refresh(event)
    db.refresh(task)
    return _to_event_read(event, task)


@router.patch("/{event_id}", response_model=EventRead)
def update_event(event_id: int, payload: EventUpdate, db: Session = Depends(get_db)):
    event = db.get(ScheduledEvent, event_id)
    if event is None or event.user_id != settings.dev_user_id:
        raise HTTPException(status_code=404, detail="Event not found")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(event, field, value)
    if event.end_time <= event.start_time:
        raise HTTPException(status_code=422, detail="end_time must be after start_time")

    event.source = "manual"
    if event.transport_schedule is not None:
        # A manually dragged transport block no longer matches the saved
        # provider itinerary. It remains on the calendar but is marked stale
        # until the user refreshes it through the transport endpoint.
        event.transport_schedule.status = "stale"
    db.commit()
    db.refresh(event)
    return _to_event_read(event, event.task)


@router.delete("/{event_id}", status_code=204)
def delete_event(event_id: int, db: Session = Depends(get_db)):
    event = db.get(ScheduledEvent, event_id)
    if event is None or event.user_id != settings.dev_user_id:
        raise HTTPException(status_code=404, detail="Event not found")

    task = event.task
    db.delete(event)
    if task is not None:
        task.status = "pending"
    db.commit()
    return None
