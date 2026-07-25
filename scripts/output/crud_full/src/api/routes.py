"""REST API routes for Task CRUD operations."""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.models.database import get_db
from src.repositories.task_repository import TaskRepository
from src.services.task_service import TaskService
from src.models.schemas import TaskCreate, TaskUpdate, TaskRead

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def get_task_service(db: Session = Depends(get_db)) -> TaskService:
    repository = TaskRepository(db)
    return TaskService(repository)


@router.get("/", response_model=list[TaskRead])
def list_tasks(
    completed: Optional[bool] = Query(None),
    service: TaskService = Depends(get_task_service),
):
    """List all tasks, optionally filtered by completion status."""
    return service.list_tasks(completed=completed)


@router.post("/", response_model=TaskRead, status_code=201)
def create_task(
    task: TaskCreate,
    service: TaskService = Depends(get_task_service),
):
    """Create a new task."""
    return service.create_task(task)


@router.get("/{task_id}", response_model=TaskRead)
def get_task(
    task_id: int,
    service: TaskService = Depends(get_task_service),
):
    """Get a single task by ID."""
    return service.get_task(task_id)


@router.put("/{task_id}", response_model=TaskRead)
def update_task(
    task_id: int,
    task: TaskUpdate,
    service: TaskService = Depends(get_task_service),
):
    """Update an existing task."""
    return service.update_task(task_id, task)


@router.delete("/{task_id}", status_code=204)
def delete_task(
    task_id: int,
    service: TaskService = Depends(get_task_service),
):
    """Delete a task."""
    service.delete_task(task_id)
