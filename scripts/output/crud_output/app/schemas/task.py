from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class TaskBase(BaseModel):
    """
    Base schema for Task data.
    """

    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    completed: bool = False


class TaskCreate(TaskBase):
    """
    Schema for creating a new Task.
    """

    pass


class TaskUpdate(BaseModel):
    """
    Schema for updating an existing Task.
    All fields are optional to allow partial updates.
    """

    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    completed: Optional[bool] = None


class TaskResponse(TaskBase):
    """
    Schema for returning Task data in API responses.
    Includes the database-generated ID and timestamp.
    """

    id: int
    created_at: datetime

    class Config:
        """
        Pydantic configuration to allow compatibility with SQLAlchemy models.
        """
        from_attributes = True