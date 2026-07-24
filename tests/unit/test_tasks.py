"""Unit tests for the tasks API endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import get_db_session
from apps.api.main import app
from core.schemas import LLMResponse


@pytest.mark.unit
class TestCreateTaskEndpoint:
    """Tests for POST /api/v1/tasks endpoint."""

    @pytest.mark.asyncio
    async def test_create_task_requires_api_key(self, client: AsyncClient) -> None:
        """Test that creating a task requires API key."""
        response = await client.post(
            "/api/v1/tasks",
            json={"description": "Create a hello world function"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_task_rejects_invalid_api_key(self, client: AsyncClient) -> None:
        """Test that invalid API key is rejected."""
        response = await client.post(
            "/api/v1/tasks",
            json={"description": "Create a hello world function"},
            headers={"X-API-Key": "invalid-key"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_create_task_empty_description(
        self, client: AsyncClient, valid_api_key: str
    ) -> None:
        """Test that empty description is rejected."""
        response = await client.post(
            "/api/v1/tasks",
            json={"description": ""},
            headers={"X-API-Key": valid_api_key},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_task_missing_description(
        self, client: AsyncClient, valid_api_key: str
    ) -> None:
        """Test that missing description field is rejected."""
        response = await client.post(
            "/api/v1/tasks",
            json={},
            headers={"X-API-Key": valid_api_key},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_task_success(
        self,
        client: AsyncClient,
        valid_api_key: str,
        mock_openrouter_response: LLMResponse,
        mock_db_session: AsyncSession,
    ) -> None:
        """Test successful task creation with mocked LLM."""
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        with patch("apps.api.routers.tasks.CoderAgent") as mock_agent_cls:
            mock_instance = AsyncMock()
            mock_instance.run.return_value = {
                "run_id": "test-run-id",
                "user_request": "Create a hello world function",
                "status": "completed",
                "generated_code": mock_openrouter_response.content,
                "tokens_used": mock_openrouter_response.tokens_used,
            }
            mock_agent_cls.return_value = mock_instance

            response = await client.post(
                "/api/v1/tasks",
                json={"description": "Create a hello world function"},
                headers={"X-API-Key": valid_api_key},
            )

            assert response.status_code == 201
            data = response.json()
            assert "id" in data
            assert data["status"] == "completed"
            assert data["generated_code"] is not None
            assert data["tokens_used"] > 0

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_create_task_handles_agent_failure(
        self, client: AsyncClient, valid_api_key: str, mock_db_session: AsyncSession
    ) -> None:
        """Test that agent failures are handled properly."""
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        with patch("apps.api.routers.tasks.CoderAgent") as mock_agent_cls:
            mock_instance = AsyncMock()
            mock_instance.run.return_value = {
                "run_id": "test-run-id",
                "status": "failed",
                "error": "LLM connection failed",
            }
            mock_agent_cls.return_value = mock_instance

            response = await client.post(
                "/api/v1/tasks",
                json={"description": "This will fail"},
                headers={"X-API-Key": valid_api_key},
            )

            assert response.status_code == 500

        app.dependency_overrides.clear()


@pytest.mark.unit
class TestGetRunEndpoint:
    """Tests for GET /api/v1/runs/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_run_requires_api_key(self, client: AsyncClient) -> None:
        """Test that getting a run requires API key."""
        response = await client.get("/api/v1/runs/test-id")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_run_not_found(
        self, client: AsyncClient, valid_api_key: str, mock_db_session: AsyncSession
    ) -> None:
        """Test that non-existent run returns 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        response = await client.get(
            "/api/v1/runs/non-existent-id",
            headers={"X-API-Key": valid_api_key},
        )
        assert response.status_code == 404

        app.dependency_overrides.clear()
