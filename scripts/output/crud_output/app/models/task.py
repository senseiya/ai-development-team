from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.core.database import Base


class Task(Base):
    """
    SQLAlchemy ORM model representing a Task in the system.

    Attributes:
        id (int): The unique identifier for the task.
        title (str): A short title or summary of the task.
        description (str): A detailed description of what needs to be done.
        completed (bool): Indicates whether the task has been finished.
        created_at (datetime): The timestamp when the task was originally created.
    """

    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, index=True)
    description = Column(String, nullable=True)
    completed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        """
        Returns a string representation of the Task instance.

        Returns:
            str: A string containing the task ID and title.
        """
        return f"<Task(id={self.id}, title='{self.title}', completed={self.completed})>"