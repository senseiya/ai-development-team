from fastapi import APIRouter, Depends, status, Query
from typing import List
from app.schemas.task import TaskCreate, TaskUpdate, TaskResponse
from app.services.task_service import TaskService
from app.repositories.task_repository import TaskRepository
from app.core.database import SessionLocal


router = APIRouter(prefix="/tasks", tags=["tasks"])


def get_task_service() -> TaskService:
    """
    Dependency provider for TaskService.
    
    Instantiates the repository and service layer for use in route handlers.
    """
    db = SessionLocal()
    try:
        repository = TaskRepository(db)
        return TaskService(repository)
    finally:
        db.close()


@router.get("/", response_model=List[TaskResponse], status_code=status.HTTP_200_OK)
def read_tasks(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    service: TaskService = Depends(get_task_service),
) -> List[TaskResponse]:
    """
    Retrieve a list of tasks with pagination support.

    - **skip**: The number of records to skip (default 0).
    - **limit**: The maximum number of records to return (default 100).
    """
    return service.get_all_tasks(skip=skip, limit=limit)


@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    task_data: TaskCreate,
    service: TaskService = Depends(get_task_service),
) -> TaskResponse:
    """
    Create a new task.

    - **task_data**: The task details including title and description.
    """
    return service.create_task(task_data)


@router.get("/{task_id}", response_model=TaskResponse, status_code=status.HTTP_200_OK)
def read_task(
    task_id: int,
    service: TaskService = Depends(get_task_service),
) -> TaskResponse:
    """
    Retrieve a specific task by its unique ID.

    - **task_id**: The ID of the task to retrieve.
    """
    return service.get_task_by_id(task_id)


@router.put("/{task_id}", response_model=TaskResponse, status_code=status.HTTP_200_OK)
def update_task(
    task_id: int,
    task_update: TaskUpdate,
    service: TaskService = Depends(get_task_service),
) -> TaskResponse:
    """
    Update an existing task.

    - **task_id**: The ID of the task to update.
    - **task_update**: The fields to update (all fields are optional).
    """
    return service.update_task(task_id, task_update)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int,
    service: TaskService = Depends(get_task_service),
) -> None:
    """
    Delete a task from the system.

    - **task_id**: The ID of the task to delete.
    """
    service.delete_task(task_id)