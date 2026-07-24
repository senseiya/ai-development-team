"""Shared test fixtures for the AI Development Team platform."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import get_current_user_id, get_db_session, verify_api_key
from apps.api.main import app
from core.schemas import LLMResponse


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create a test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def authenticated_client(
    mock_db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with auth bypassed and DB mocked.

    Use this fixture for testing any protected endpoint (those that use
    Depends(verify_api_key) or Depends(get_current_user_id)) without
    having to manually set up dependency_overrides in each test.
    """
    app.dependency_overrides[get_db_session] = lambda: mock_db_session
    app.dependency_overrides[verify_api_key] = lambda: "test-api-key"
    app.dependency_overrides[get_current_user_id] = lambda: "test-user-id"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def authenticated_client_with_db() -> AsyncGenerator[tuple[AsyncClient, AsyncSession], None]:
    """Create an (client, mock_db_session) tuple with auth bypassed.

    Use this when you need to configure specific mock return values on
    the database session for each test case.
    """
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()

    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[verify_api_key] = lambda: "test-api-key"
    app.dependency_overrides[get_current_user_id] = lambda: "test-user-id"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, session

    app.dependency_overrides.clear()


@pytest.fixture
def mock_db_session() -> AsyncSession:
    """Create a mock database session."""
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def mock_openrouter_response() -> LLMResponse:
    """Create a mock OpenRouter response."""
    return LLMResponse(
        content='def hello_world():\n    """Print hello world."""\n    print("Hello, World!")',
        model="qwen/qwen-2.5-coder-32b-instruct:free",
        tokens_used=50,
        finish_reason="stop",
    )


@pytest.fixture
def mock_openrouter_provider(mock_openrouter_response: LLMResponse) -> MagicMock:
    """Create a mock OpenRouter provider."""
    provider = MagicMock()
    provider.complete = AsyncMock(return_value=mock_openrouter_response)
    return provider


@pytest.fixture
def valid_api_key() -> str:
    """Return a valid API key for testing."""
    return "change-me-in-production"


@pytest.fixture
def invalid_api_key() -> str:
    """Return an invalid API key for testing."""
    return "invalid-key-12345"
