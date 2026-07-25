import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Base class for SQLAlchemy models.
    """
    pass


class Task(Base):
    """
    SQLAlchemy ORM model representing a Task entity.

    Attributes:
        id (int): The unique identifier for the task.
        title (str): The title of the task.
        description (str): A detailed description of the task.
        completed (bool): The completion status of the task.
        created_at (datetime): The timestamp when the task was created.
    """

    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    completed = Column(Boolean, default=False)
    created_at = Column(
        DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<Task(id={self.id}, title='{self.title}', completed={self.completed})>"