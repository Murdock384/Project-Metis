from datetime import datetime

from pydantic import BaseModel, Field


class TaskBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    difficulty: int = Field(default=3, ge=1, le=5)
    urgency: int = Field(default=3, ge=1, le=5)
    estimated_minutes: int = Field(default=30, gt=0, le=24 * 60)
    category: str | None = Field(default=None, max_length=60)


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    difficulty: int | None = Field(default=None, ge=1, le=5)
    urgency: int | None = Field(default=None, ge=1, le=5)
    estimated_minutes: int | None = Field(default=None, gt=0, le=24 * 60)
    category: str | None = Field(default=None, max_length=60)
    status: str | None = None


class TaskRead(TaskBase):
    id: int
    user_id: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
