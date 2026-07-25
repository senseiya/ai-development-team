import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Task(Base):
    """
    SQLAlchemy ORM model representing a Task in the system.

    Attributes:
        id (int): The unique identifier for the task.
        title (str): A short summary of the task.
        description (str): A detailed description of the task.
        completed (bool): Flag indicating if the task is finished.
        created_at (datetime): The timestamp when the task was created.
    """

    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(String(1024), nullable=True)
    completed = Column(Boolean, default=False, nullable=False)
    created_at = Column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        """
        Returns a string representation of the Task instance.

        Returns:
            str: A string containing the task ID and title.
        """
        return f"<Task(id={self.id}, title='{self.title}', completed={self.completed})>"