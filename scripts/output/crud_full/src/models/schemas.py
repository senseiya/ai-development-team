from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class TaskBase(BaseModel):
    """Base schema for Task properties common to all DTOs."""

    title: str = Field(..., min_length=1, max_length=100, description="The title of the task")
    description: Optional[str] = Field(None, max_length=500, description="Detailed description of the task")
    is_completed: bool = Field(default=False, description="Status of task completion")


class TaskCreate(TaskBase):
    """DTO for creating a new task."""

    pass


class TaskUpdate(BaseModel):
    """DTO for updating an existing task. All fields are optional."""

    title: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    is_completed: Optional[bool] = None


class TaskRead(TaskBase):
    """DTO for returning task data in API responses."""

    id: int
    created_at: datetime

    class Config:
        """Pydantic configuration to allow reading from ORM models."""
        from_attributes = True