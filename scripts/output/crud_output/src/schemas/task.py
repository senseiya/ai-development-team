from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class TaskBase(BaseModel):
    """Base properties for a task."""

    title: str = Field(..., min_length=1, max_length=255, description="The title of the task")
    description: Optional[str] = Field(None, max_length=1000, description="Detailed description of the task")
    is_completed: bool = Field(default=False, description="Status indicating if the task is finished")


class TaskCreate(TaskBase):
    """DTO for creating a new task."""

    title: str = Field(..., min_length=1, max_length=255)


class TaskUpdate(BaseModel):
    """DTO for updating an existing task. All fields are optional."""

    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    is_completed: Optional[bool] = None


class TaskRead(TaskBase):
    """DTO for returning task data in API responses."""

    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        """Pydantic configuration for ORM compatibility."""

        from_attributes = True