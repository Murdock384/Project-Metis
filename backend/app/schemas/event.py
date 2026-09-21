from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class EventCreate(BaseModel):
    """Manual quick-add. Either reference an existing task via `task_id`,
    or provide inline task fields to create a brand-new ad-hoc task."""

    task_id: int | None = None
    title: str | None = Field(default=None, max_length=200)
    difficulty: int = Field(default=3, ge=1, le=5)
    urgency: int = Field(default=3, ge=1, le=5)
    category: str | None = Field(default=None, max_length=60)

    start_time: datetime
    end_time: datetime

    @model_validator(mode="after")
    def check_task_reference(self):
        if self.task_id is None and not self.title:
            raise ValueError("Either task_id or title must be provided")
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class EventUpdate(BaseModel):
    start_time: datetime | None = None
    end_time: datetime | None = None

    @model_validator(mode="after")
    def check_range(self):
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class EventRead(BaseModel):
    id: int
    task_id: int | None
    task_title: str | None
    title: str
    event_type: str
    category: str | None
    start_time: datetime
    end_time: datetime
    source: str
    calendar_event_id: str | None

    model_config = {"from_attributes": True}


class ScheduleRunResult(BaseModel):
    scheduled_count: int
    skipped_count: int
    events: list[EventRead]
