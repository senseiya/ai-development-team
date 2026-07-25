from typing import List, Optional
from fastapi import HTTPException, status
from src.repositories.task_repository import TaskRepository
from src.models.schemas import TaskCreate, TaskUpdate, TaskRead


class TaskService:
    """
    Service layer for managing task business logic.

    This class acts as an intermediary between the API controllers and the
    repository layer. It handles data transformation (DTOs) and implements
    business rules and error handling.
    """

    def __init__(self, repository: TaskRepository) -> None:
        """
        Initializes the TaskService with a TaskRepository.

        Args:
            repository (TaskRepository): The repository instance for task operations.
        """
        self.repository = repository

    def create_task(self, task_dto: TaskCreate) -> TaskRead:
        """
        Validates and creates a new task.

        Args:
            task_dto (TaskCreate): Data transfer object containing task details.

        Returns:
            TaskRead: The created task as a read-only DTO.

        Raises:
            HTTPException: If task creation fails (though unlikely for simple CRUD).
        """
        # Mapping DTO to dictionary for repository compatibility
        # Note: Mapping 'is_completed' from schema to 'completed' for the DB model
        task_data = {
            "title": task_dto.title,
            "description": task_dto.description,
            "completed": task_dto.is_completed,
        }
        
        new_task = self.repository.create(task_data)
        return self._to_read_dto(new_task)

    def get_task(self, task_id: int) -> TaskRead:
        """
        Retrieves a single task by ID.

        Args:
            task_id (int): The unique identifier of the task.

        Returns:
            TaskRead: The task data as a DTO.

        Raises:
            HTTPException: 404 error if the task does not exist.
        """
        task = self.repository.get_by_id(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task with id {task_id} not found"
            )
        return self._to_read_dto(task)

    def list_tasks(self, completed: Optional[bool] = None) -> List[TaskRead]:
        """
        Retrieves all tasks, optionally filtered by completion status.

        Args:
            completed (Optional[bool]): Filter tasks by completion status.

        Returns:
            List[TaskRead]: A list of task DTOs.
        """
        tasks = self.repository.get_all(completed=completed)
        return [self._to_read_dto(task) for task in tasks]

    def update_task(self, task_id: int, task_dto: TaskUpdate) -> TaskRead:
        """
        Updates an existing task.

        Args:
            task_id (int): The ID of the task to update.
            task_dto (TaskUpdate): DTO containing the updated fields.

        Returns:
            TaskRead: The updated task as a DTO.

        Raises:
            HTTPException: 404 error if the task does not exist.
        """
        # Mapping DTO fields to match the repository/model field names
        update_data = {}
        if task_dto.title is not None:
            update_data["title"] = task_dto.title
        if task_dto.description is not None:
            update_data["description"] = task_dto.description
        if task_dto.is_completed is not None:
            update_data["completed"] = task_dto.is_completed

        updated_task = self.repository.update(task_id, update_data)
        if not updated_task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task with id {task_id} not found"
            )
        return self._to_read_dto(updated_task)

    def delete_task(self, task_id: int) -> None:
        """
        Deletes a task from the system.

        Args:
            task_id (int): The ID of the task to delete.

        Raises:
            HTTPException: 404 error if the task does not exist.
        """
        success = self.repository.delete(task_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task with id {task_id} not found"
            )

    def _to_read_dto(self, task_model: any) -> TaskRead:
        """
        Internal helper to transform the SQLAlchemy model to a TaskRead DTO.

        Args:
            task_model: The SQLAlchemy Task instance.

        Returns:
            TaskRead: The transformed DTO.
        """
        return TaskRead(
            id=task_model.id,
            title=task_model.title,
            description=task_model.description,
            is_completed=task_model.completed,
            created_at=task_model.created_at,
        )