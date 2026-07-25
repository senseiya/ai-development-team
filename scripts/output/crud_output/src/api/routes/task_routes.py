from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from src.core.database import get_db
from src.schemas.task import TaskCreate, TaskRead, TaskUpdate
from src.services.task_service import TaskService


router = APIRouter(prefix="/tasks", tags=["tasks"])


def get_task_service(db: Session = Depends(get_db)) -> TaskService:
    """
    Dependency provider for TaskService.

    Args:
        db (Session): The database session provided by the dependency injection system.

    Returns:
        TaskService: An instance of TaskService.
    """
    return TaskService(db)


@router.post(
    "",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new task",
    description="Creates a new task in the database.",
)
def create_task(
    task_data: TaskCreate,
    service: TaskService = Depends(get_task_service),
) -> TaskRead:
    """
    Endpoint to create a new task.
    """
    try:
        return service.create_task(task_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating the task: {str(e)}",
        )


@router.get(
    "",
    response_model=List[TaskRead],
    summary="Get all tasks",
    description="Retrieves a list of tasks with optional pagination.",
)
def read_tasks(
    skip: int = 0,
    limit: int = 100,
    service: TaskService = Depends(get_task_service),
) -> List[TaskRead]:
    """
    Endpoint to retrieve all tasks.
    """
    return service.get_all_tasks(skip=skip, limit=limit)


@router.get(
    "/{task_id}",
    response_model=TaskRead,
    summary="Get a task by ID",
    description="Retrieves a single task by its unique identifier.",
)
def read_task(
    task_id: int,
    service: TaskService = Depends(get_task_service),
) -> TaskRead:
    """
    Endpoint to retrieve a specific task.
    """
    task = service.get_task_by_id(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID {task_id} not found",
        )
    return task


@router.patch(
    "/{task_id}",
    response_model=TaskRead,
    summary="Update a task",
    description="Updates an existing task's information.",
)
def update_task(
    task_id: int,
    task_update: TaskUpdate,
    service: TaskService = Depends(get_task_service),
) -> TaskRead:
    """
    Endpoint to update an existing task.
    """
    updated_task = service.update_task(task_id, task_update)
    if not updated_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID {task_id} not found",
        )
    return updated_task


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task",
    description="Deletes a task from the database.",
)
def delete_task(
    task_id: int,
    service: TaskService = Depends(get_task_service),
) -> None:
    """
    Endpoint to delete a task.
    """
    success = service.delete_task(task_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID {task_id} not found",
        )
    return None