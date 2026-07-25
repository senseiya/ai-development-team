from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from src.core.database import get_db
from src.services.task_service import TaskService


router = APIRouter()
templates = Jinja2Templates(directory="templates")


def get_task_service(db: Session = Depends(get_db)) -> TaskService:
    """
    Dependency provider for TaskService.

    Args:
        db (Session): The database session.

    Returns:
        TaskService: An instance of TaskService.
    """
    return TaskService(db)


@router.get("/", response_class=HTMLResponse)
async def render_dashboard(
    request: Request,
    task_service: TaskService = Depends(get_task_service),
) -> HTMLResponse:
    """
    Renders the main dashboard page showing the list of tasks.

    Args:
        request (Request): The FastAPI request object.
        task_service (TaskService): The service layer instance for tasks.

    Returns:
        HTMLResponse: The rendered dashboard HTML.
    """
    tasks = task_service.get_all_tasks()
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "tasks": tasks},
    )


@router.get("/task/{task_id}", response_class=HTMLResponse)
async def render_task_details(
    request: Request,
    task_id: int,
    task_service: TaskService = Depends(get_task_service),
) -> HTMLResponse:
    """
    Renders the task details page.

    Args:
        request (Request): The FastAPI request object.
        task_id (int): The ID of the task to view.
        task_service (TaskService): The service layer instance for tasks.

    Returns:
        HTMLResponse: The rendered task details HTML.
    """
    task = task_service.get_task_by_id(task_id)
    if not task:
        return templates.TemplateResponse(
            "404.html",
            {"request": request, "error": "Task not found"},
        )

    return templates.TemplateResponse(
        "task_details.html",
        {"request": request, "task": task},
    )