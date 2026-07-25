from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskUpdate


class TaskRepository:
    """
    Repository for performing CRUD operations on the Task model.

    This class encapsulates all direct database interactions for Task entities,
    abstracting the SQLAlchemy session logic from the service layer.
    """

    def __init__(self, db: Session):
        """
        Initializes the TaskRepository with a database session.

        Args:
            db (Session): The SQLAlchemy database session.
        """
        self.db = db

    def get_by_id(self, task_id: int) -> Optional[Task]:
        """
        Retrieve a single task by its unique identifier.

        Args:
            task_id (int): The ID of the task to retrieve.

        Returns:
            Optional[Task]: The Task object if found, otherwise None.
        """
        return self.db.query(Task).filter(Task.id == task_id).first()

    def get_all(self, skip: int = 0, limit: int = 100) -> List[Task]:
        """
        Retrieve a list of tasks with pagination.

        Args:
            skip (int): The number of records to skip (offset).
            limit (int): The maximum number of records to return.

        Returns:
            List[Task]: A list of Task objects.
        """
        return self.db.query(Task).offset(skip).limit(limit).all()

    def create(self, task_data: TaskCreate) -> Task:
        """
        Create a new task in the database.

        Args:
            task_data (TaskCreate): The DTO containing task details.

        Returns:
            Task: The newly created Task object.
        """
        db_task = Task(
            title=task_data.title,
            description=task_data.description,
            completed=task_data.completed,
        )
        self.db.add(db_task)
        self.db.commit()
        self.db.refresh(db_task)
        return db_task

    def update(self, task_id: int, task_update: TaskUpdate) -> Optional[Task]:
        """
        Update an existing task.

        Args:
            task_id (int): The ID of the task to update.
            task_update (TaskUpdate): The DTO containing updated fields.

        Returns:
            Optional[Task]: The updated Task object, or None if not found.
        """
        db_task = self.get_by_id(task_id)
        if not db_task:
            return None

        update_data = task_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_task, key, value)

        self.db.commit()
        self.db.refresh(db_task)
        return db_task

    def delete(self, task_id: int) -> bool:
        """
        Delete a task from the database.

        Args:
            task_id (int): The ID of the task to delete.

        Returns:
            bool: True if the task was deleted, False if the task was not found.
        """
        db_task = self.get_by_id(task_id)
        if not db_task:
            return False

        self.db.delete(db_task)
        self.db.commit()
        return True