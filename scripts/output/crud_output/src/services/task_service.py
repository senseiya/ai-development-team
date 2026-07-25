from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import exc
from src.models.task import Task
from src.schemas.task import TaskCreate, TaskUpdate


class TaskService:
    """
    Service layer for handling business logic related to Tasks.

    This class encapsulates all business rules and interacts with the
    repository/database layer to perform CRUD operations.
    """

    def __init__(self, db: Session):
        """
        Initializes the TaskService with a database session.

        Args:
            db (Session): The SQLAlchemy database session.
        """
        self.db = db

    def create_task(self, task_data: TaskCreate) -> Task:
        """
        Creates a new task in the database.

        Args:
            task_data (TaskCreate): The DTO containing task details.

        Returns:
            Task: The newly created Task ORM object.

        Raises:
            Exception: If a database error occurs during creation.
        """
        try:
            new_task = Task(
                title=task_data.title,
                description=task_data.description,
                completed=task_data.is_completed,
            )
            self.db.add(new_task)
            self.db.commit()
            self.db.refresh(new_task)
            return new_task
        except exc.SQLAlchemyError as e:
            self.db.rollback()
            raise e

    def get_task_by_id(self, task_id: int) -> Optional[Task]:
        """
        Retrieves a single task by its unique identifier.

        Args:
            task_id (int): The ID of the task to retrieve.

        Returns:
            Optional[Task]: The Task object if found, otherwise None.
        """
        return self.db.query(Task).filter(Task.id == task_id).first()

    def get_all_tasks(self, skip: int = 0, limit: int = 100) -> List[Task]:
        """
        Retrieves a list of tasks with pagination.

        Args:
            skip (int): The number of records to skip.
            limit (int): The maximum number of records to return.

        Returns:
            List[Task]: A list of Task ORM objects.
        """
        return self.db.query(Task).offset(skip).limit(limit).all()

    def update_task(self, task_id: int, task_update: TaskUpdate) -> Optional[Task]:
        """
        Updates an existing task's information.

        Args:
            task_id (int): The ID of the task to update.
            task_update (TaskUpdate): The DTO containing updated fields.

        Returns:
            Optional[Task]: The updated Task ORM object, or None if not found.

        Raises:
            Exception: If a database error occurs during update.
        """
        db_task = self.get_task_by_id(task_id)
        if not db_task:
            return None

        try:
            update_data = task_update.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                # Mapping schema field 'is_completed' to model field 'completed'
                if key == "is_completed":
                    db_task.completed = value
                else:
                    setattr(db_task, key, value)

            self.db.commit()
            self.db.refresh(db_task)
            return db_task
        except exc.SQLAlchemyError as e:
            self.db.rollback()
            raise e

    def delete_task(self, task_id: int) -> bool:
        """
        Deletes a task from the database.

        Args:
            task_id (int): The ID of the task to delete.

        Returns:
            bool: True if the task was deleted, False if not found.

        Raises:
            Exception: If a database error occurs during deletion.
        """
        db_task = self.get_task_by_id(task_id)
        if not db_task:
            return False

        try:
            self.db.delete(db_task)
            self.db.commit()
            return True
        except exc.SQLAlchemyError as e:
            self.db.rollback()
            raise e