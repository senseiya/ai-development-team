from typing import List, Optional
from fastapi import HTTPException, status
from app.repositories.task_repository import TaskRepository
from app.schemas.task import TaskCreate, TaskUpdate, TaskResponse


class TaskService:
    """
    Service layer for Task business logic.

    This class acts as an intermediary between the API controllers and the
    repository layer, handling business rules, validation logic, and
    mapping between database models and DTOs.
    """

    def __init__(self, repository: TaskRepository):
        """
        Initializes the TaskService with a repository.

        Args:
            repository (TaskRepository): The repository instance used for data access.
        """
        self.repository = repository

    def get_all_tasks(self, skip: int = 0, limit: int = 100) -> List[TaskResponse]:
        """
        Retrieves all tasks with pagination.

        Args:
            skip (int): Number of records to skip.
            limit (int): Maximum number of records to return.

        Returns:
            List[TaskResponse]: A list of task responses.
        """
        tasks = self.repository.get_all(skip=skip, limit=limit)
        return [TaskResponse.model_validate(task) for task in tasks]

    def get_task_by_id(self, task_id: int) -> TaskResponse:
        """
        Retrieves a single task by its ID.

        Args:
            task_id (int): The unique identifier of the task.

        Returns:
            TaskResponse: The requested task.

        Raises:
            HTTPException: 404 error if the task is not found.
        """
        task = self.repository.get_by_id(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task with id {task_id} not found"
            )
        return TaskResponse.model_validate(task)

    def create_task(self, task_data: TaskCreate) -> TaskResponse:
        """
        Creates a new task.

        Args:
            task_data (TaskCreate): The DTO containing task creation details.

        Returns:
            TaskResponse: The newly created task.
        """
        # Business logic: Ensure title is not just whitespace (handled by Pydantic, 
        # but could be expanded here for more complex domain rules).
        new_task = self.repository.create(task_data)
        return TaskResponse.model_validate(new_task)

    def update_task(self, task_id: int, task_update: TaskUpdate) -> TaskResponse:
        """
        Updates an existing task.

        Args:
            task_id (int): The ID of the task to update.
            task_update (TaskUpdate): The DTO containing updated fields.

        Returns:
            TaskResponse: The updated task.

        Raises:
            HTTPException: 404 error if the task is not found.
        """
        updated_task = self.repository.update(task_id, task_update)
        if not updated_task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task with id {task_id} not found"
            )
        return TaskResponse.model_validate(updated_task)

    def delete_task(self, task_id: int) -> None:
        """
        Deletes a task.

        Args:
            task_id (int): The ID of the task to delete.

        Raises:
            HTTPException: 404 error if the task is not found.
        """
        success = self.repository.delete(task_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task with id {task_id} not found"
            )