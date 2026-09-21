from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.endpoints.preferences import get_or_create_preference
from app.core.config import settings
from app.db.base import get_db
from app.models.scheduled_event import ScheduledEvent
from app.models.task import Task
from app.schemas.event import EventRead, ScheduleRunResult
from app.schemas.task import TaskCreate, TaskRead, TaskUpdate
from app.services.scheduler_service import (
    BusyBlock,
    SchedulableTask,
    SchedulerPreferences,
    schedule_pending_tasks,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=TaskRead, status_code=201)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)):
    task = Task(user_id=settings.dev_user_id, **payload.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("", response_model=list[TaskRead])
def list_tasks(status: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Task).where(Task.user_id == settings.dev_user_id)
    if status:
        stmt = stmt.where(Task.status == status)
    stmt = stmt.order_by(Task.created_at.desc())
    return db.scalars(stmt).all()


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if task is None or task.user_id != settings.dev_user_id:
        raise HTTPException(status_code=404, detail="Task not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if task is None or task.user_id != settings.dev_user_id:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
    return None


@router.post("/schedule", response_model=ScheduleRunResult)
def run_scheduler(db: Session = Depends(get_db)):
    """Run the OR-Tools scheduler over all pending tasks for the dev user,
    creating `ScheduledEvent` rows for whatever it manages to fit."""
    pending_tasks = db.scalars(
        select(Task).where(Task.user_id == settings.dev_user_id, Task.status == "pending")
    ).all()

    existing_events = db.scalars(
        select(ScheduledEvent).where(ScheduledEvent.user_id == settings.dev_user_id)
    ).all()

    if not pending_tasks:
        return ScheduleRunResult(scheduled_count=0, skipped_count=0, events=[])

    schedulable = [
        SchedulableTask(
            id=t.id,
            urgency=t.urgency,
            difficulty=t.difficulty,
            estimated_minutes=t.estimated_minutes,
            category=t.category,
        )
        for t in pending_tasks
    ]
    busy = [BusyBlock(start_time=e.start_time, end_time=e.end_time) for e in existing_events]

    preference = get_or_create_preference(db)
    prefs = SchedulerPreferences(
        work_start_hour=preference.work_start_hour,
        work_end_hour=preference.work_end_hour,
        horizon_days=preference.horizon_days,
        slot_minutes=preference.slot_minutes,
        peak_focus_start_hour=preference.peak_focus_start_hour,
        peak_focus_end_hour=preference.peak_focus_end_hour,
        min_break_minutes=preference.min_break_minutes,
        max_daily_task_minutes=preference.max_daily_task_minutes,
        preferred_categories=list(preference.preferred_categories or []),
        disliked_categories=list(preference.disliked_categories or []),
    )

    results = schedule_pending_tasks(schedulable, busy, prefs)

    created_events: list[ScheduledEvent] = []
    scheduled_count = 0
    skipped_count = 0
    tasks_by_id = {t.id: t for t in pending_tasks}

    for result in results:
        task = tasks_by_id[result.task_id]
        if not result.scheduled:
            skipped_count += 1
            continue
        event = ScheduledEvent(
            task_id=task.id,
            user_id=settings.dev_user_id,
            title=task.title,
            event_type="task",
            start_time=result.start_time,
            end_time=result.end_time,
            source="scheduler",
        )
        task.status = "scheduled"
        db.add(event)
        created_events.append(event)
        scheduled_count += 1

    db.commit()
    for event in created_events:
        db.refresh(event)

    events_read = [
        EventRead(
            id=e.id,
            task_id=e.task_id,
            task_title=tasks_by_id[e.task_id].title,
            title=e.title,
            event_type=e.event_type,
            category=tasks_by_id[e.task_id].category,
            start_time=e.start_time,
            end_time=e.end_time,
            source=e.source,
            calendar_event_id=e.calendar_event_id,
        )
        for e in created_events
    ]

    return ScheduleRunResult(
        scheduled_count=scheduled_count, skipped_count=skipped_count, events=events_read
    )
