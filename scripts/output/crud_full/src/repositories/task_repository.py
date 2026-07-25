from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from src.models.task import Task


class TaskRepository:
    """
    Repository class for performing CRUD operations on Task entities using SQLAlchemy.

    This class abstracts the database access logic, providing a clean interface
    for the service layer to interact with the Task model.
    """

    def __init__(self, db: Session) -> None:
        """
        Initializes the TaskRepository with a database session.

        Args:
            db (Session): The SQLAlchemy database session.
        """
        self.db = db

    def create(self, task_data: dict) -> Task:
        """
        Creates a new task in the database.

        Args:
            task_data (dict): A dictionary containing the task attributes 
                (e.g., title, description).

        Returns:
            Task: The newly created Task instance.
        """
        db_task = Task(
            title=task_data["title"],
            description=task_data.get("description"),
            completed=task_data.get("completed", False),
        )
        self.db.add(db_task)
        self.db.commit()
        self.db.refresh(db_task)
        return db_task

    def get_by_id(self, task_id: int) -> Optional[Task]:
        """
        Retrieves a task by its unique identifier.

        Args:
            task_id (int): The ID of the task to retrieve.

        Returns:
            Optional[Task]: The Task object if found, otherwise None.
        """
        return self.db.query(Task).filter(Task.id == task_id).first()

    def get_all(self, completed: Optional[bool] = None) -> List[Task]:
        """
        Retrieves all tasks, optionally filtered by completion status.

        Args:
            completed (Optional[bool]): Filter tasks by their completion status.

        Returns:
            List[Task]: A list of Task objects.
        """
        query = select(Task)
        if completed is not None:
            query = query.where(Task.completed == completed)

        result = self.db.execute(query)
        return result.scalars().all()

    def update(self, task_id: int, task_data: dict) -> Optional[Task]:
        """
        Updates an existing task with the provided data.

        Args:
            task_id (int): The ID of the task to update.
            task_data (dict): A dictionary containing the updated attributes.

        Returns:
            Optional[Task]: The updated Task object, or None if not found.
        """
        db_task = self.get_by_id(task_id)
        if not db_task:
            return None

        for key, value in task_data.items():
            if hasattr(db_task, key):
                setattr(db_task, key, value)

        self.db.commit()
        self.db.refresh(db_task)
        return db_task

    def delete(self, task_id: int) -> bool:
        """
        Deletes a task from the database.

        Args:
            task_id (int): The ID of the task to delete.

        Returns:
            bool: True if the task was deleted, False if not found.
        """
        db_task = self.get_by_id(task_id)
        if not db_task:
            return False

        self.db.delete(db_task)
        self.db.commit()
        return True