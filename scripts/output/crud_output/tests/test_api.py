import pytest
from httpx import AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testlib import TestingClient

from main import app
from app.core.database import Base

# Test database configuration (using SQLite in-memory for isolation)
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    """
    Provides a clean database session for each test case.
    """
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture
async def client():
    """
    Provides an AsyncClient for testing API endpoints.
    """
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """
    Test the health check endpoint.
    """
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

@pytest.mark.asyncio
async def test_get_tasks_empty(client: AsyncClient):
    """
    Test retrieving tasks when the list is empty.
    """
    response = await client.get("/api/tasks")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) == 0

@pytest.mark.asyncio
async def test_create_task_success(client: AsyncClient):
    """
    Test creating a new task via API.
    """
    payload = {
        "title": "Test Task",
        "description": "This is a test description",
        "completed": False
    }
    response = await client.post("/api/tasks", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == payload["title"]
    assert data["description"] == payload["description"]
    assert data["completed"] is False
    assert "id" in data
    assert "created_at" in data

@pytest.mark.asyncio
async def test_create_task_invalid_data(client: AsyncClient):
    """
    Test creating a task with invalid data (missing title).
    """
    payload = {
        "description": "Missing title",
        "completed": False
    }
    response = await client.post("/api/tasks", json=payload)
    assert response.status_code == 422  # Unprocessable Entity

@pytest.mark.asyncio
async def test_get_single_task(client: AsyncClient):
    """
    Test retrieving a specific task by ID.
    """
    # First, create a task
    create_res = await client.post("/api/tasks", json={"title": "Target Task"})
    task_id = create_res.json()["id"]

    # Then, fetch it
    response = await client.get(f"/api/tasks/{task_id}")
    assert response.status_code == 200
    assert response.json()["title"] == "Target Task"

@pytest.mark.asyncio
async def test_get_nonexistent_task(client: AsyncClient):
    """
    Test retrieving a task that does not exist.
    """
    response = await client.get("/api/tasks/9999")
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_update_task_partial(client: AsyncClient):
    """
    Test updating a task using partial data.
    """
    # Create initial task
    create_res = await client.post("/api/tasks", json={"title": "Old Title", "completed": False})
    task_id = create_res.json()["id"]

    # Update only the completed status
    update_payload = {"completed": True}
    response = await client.patch(f"/api/tasks/{task_id}", json=update_payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Old Title"
    assert data["completed"] is True

@pytest.mark.asyncio
async def test_update_task_full(client: AsyncClient):
    """
    Test updating a task with all fields.
    """
    create_res = await client.post("/api/tasks", json={"title": "Old Title"})
    task_id = create_res.json()["id"]

    update_payload = {
        "title": "New Title",
        "description": "New Description",
        "completed": True
    }
    response = await client.put(f"/api/tasks/{task_id}", json=update_payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "New Title"
    assert data["description"] == "New Description"
    assert data["completed"] is True

@pytest.mark.asyncio
async def test_delete_task(client: AsyncClient):
    """
    Test deleting a task.
    """
    # Create task
    create_res = await client.post("/api/tasks", json={"title": "To be deleted"})
    task_id = create_res.json()["id"]

    # Delete task
    delete_res = await client.delete(f"/api/tasks/{task_id}")
    assert delete_res.status_code == 204

    # Verify it's gone
    get_res = await client.get(f"/api/tasks/{task_id}")
    assert get_res.status_code == 404

@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """
    Test the root endpoint returns HTML (simulated by checking content type).
    """
    response = await client.get("/")
    assert response.status_code == 200
    # FastAPI returns content-type for templates as text/html
    assert "text/html" in response.headers["content-type"]