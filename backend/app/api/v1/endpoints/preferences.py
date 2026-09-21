from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import get_db
from app.models.user_preference import UserPreference
from app.schemas.user_preference import (
    UserPreferenceRead,
    UserPreferenceUpdate,
    coherence_error,
)

router = APIRouter(prefix="/preferences", tags=["preferences"])

EDITABLE_FIELDS = (
    "timezone",
    "work_start_hour",
    "work_end_hour",
    "horizon_days",
    "slot_minutes",
    "peak_focus_start_hour",
    "peak_focus_end_hour",
    "min_break_minutes",
    "max_daily_task_minutes",
    "preferred_categories",
    "disliked_categories",
)


def get_or_create_preference(db: Session) -> UserPreference:
    """Preferences are created on first read, seeded from `Settings`, so the
    endpoint (and the scheduler) can always assume a row exists."""
    preference = db.scalar(
        select(UserPreference).where(UserPreference.user_id == settings.dev_user_id)
    )
    if preference is not None:
        return preference

    preference = UserPreference(
        user_id=settings.dev_user_id,
        work_start_hour=settings.work_start_hour,
        work_end_hour=settings.work_end_hour,
        horizon_days=settings.horizon_days,
        slot_minutes=settings.slot_minutes,
        peak_focus_start_hour=settings.peak_focus_start_hour,
        peak_focus_end_hour=settings.peak_focus_end_hour,
        min_break_minutes=settings.min_break_minutes,
        max_daily_task_minutes=settings.max_daily_task_minutes,
        timezone=settings.user_timezone,
        preferred_categories=[],
        disliked_categories=[],
    )
    db.add(preference)
    db.commit()
    db.refresh(preference)
    return preference


@router.get("", response_model=UserPreferenceRead)
def read_preferences(db: Session = Depends(get_db)):
    return get_or_create_preference(db)


@router.patch("", response_model=UserPreferenceRead)
def update_preferences(payload: UserPreferenceUpdate, db: Session = Depends(get_db)):
    preference = get_or_create_preference(db)
    updates = payload.model_dump(exclude_unset=True)

    merged = {field: getattr(preference, field) for field in EDITABLE_FIELDS}
    merged.update(updates)

    error = coherence_error(merged)
    if error is not None:
        raise HTTPException(status_code=422, detail=error)

    for field, value in updates.items():
        setattr(preference, field, value)
    db.commit()
    db.refresh(preference)
    return preference
