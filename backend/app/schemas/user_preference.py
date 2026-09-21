from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator


class UserPreferenceUpdate(BaseModel):
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    work_start_hour: int | None = Field(default=None, ge=0, le=23)
    work_end_hour: int | None = Field(default=None, ge=1, le=24)
    horizon_days: int | None = Field(default=None, ge=1, le=30)
    slot_minutes: int | None = Field(default=None, ge=5, le=120)

    peak_focus_start_hour: int | None = Field(default=None, ge=0, le=23)
    peak_focus_end_hour: int | None = Field(default=None, ge=1, le=24)

    min_break_minutes: int | None = Field(default=None, ge=0, le=120)
    max_daily_task_minutes: int | None = Field(default=None, ge=15, le=24 * 60)

    preferred_categories: list[str] | None = None
    disliked_categories: list[str] | None = None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone must be a valid IANA timezone, e.g. Europe/Warsaw") from exc
        return value


class UserPreferenceRead(BaseModel):
    id: int
    user_id: int

    work_start_hour: int
    work_end_hour: int
    horizon_days: int
    slot_minutes: int

    peak_focus_start_hour: int
    peak_focus_end_hour: int

    min_break_minutes: int
    max_daily_task_minutes: int
    timezone: str

    preferred_categories: list[str]
    disliked_categories: list[str]

    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


def coherence_error(values: dict) -> str | None:
    """Cross-field checks that a PATCH can only be validated against once
    merged with the stored row. Returns None when the combination is valid.
    """
    work_start = values["work_start_hour"]
    work_end = values["work_end_hour"]
    slot_minutes = values["slot_minutes"]
    focus_start = values["peak_focus_start_hour"]
    focus_end = values["peak_focus_end_hour"]

    if work_end <= work_start:
        return "work_end_hour must be after work_start_hour"

    working_minutes = (work_end - work_start) * 60
    if working_minutes % slot_minutes != 0:
        # _Horizon divides the day into whole slots; a remainder would
        # silently drop the tail of every day.
        return f"slot_minutes must divide evenly into the {working_minutes}-minute working day"

    if focus_end <= focus_start:
        return "peak_focus_end_hour must be after peak_focus_start_hour"

    if focus_start < work_start or focus_end > work_end:
        return "the focus window must fall inside working hours"

    if values["min_break_minutes"] % slot_minutes != 0:
        return "min_break_minutes must be a multiple of slot_minutes"

    return None
