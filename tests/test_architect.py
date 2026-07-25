"""Tests for ArchitectAgent and ProjectBlueprint."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from core.agents.architect import FALLBACK_BLUEPRINT, ArchitectAgent
from core.orchestrator.state import AgentState, ProjectBlueprint, create_initial_state
from core.schemas import LLMResponse


@pytest.fixture
def architect() -> ArchitectAgent:
    return ArchitectAgent()


@pytest.fixture
def base_state() -> AgentState:
    return create_initial_state(
        run_id="test-arch-123",
        user_request="Build a REST API for a task manager with PostgreSQL",
    )


# --- ProjectBlueprint Tests ---


class TestProjectBlueprint:
    def test_defaults(self):
        bp = ProjectBlueprint()
        assert bp.project_name == ""
        assert bp.backend == ""
        assert bp.patterns == []
        assert bp.docker is False

    def test_to_human_readable(self):
        bp = ProjectBlueprint(
            project_name="TaskManager",
            project_type="web_api",
            backend="FastAPI",
            backend_language="python",
            database="PostgreSQL",
            orm="SQLAlchemy",
            authentication="JWT",
            architecture="layered",
            patterns=["Repository", "Service Layer"],
            testing=["pytest", "httpx"],
            linting=["ruff"],
            docker=True,
            directory_structure=["src/", "src/models/", "tests/"],
        )
        text = bp.to_human_readable()
        assert "TaskManager" in text
        assert "FastAPI" in text
        assert "PostgreSQL" in text
        assert "SQLAlchemy" in text
        assert "JWT" in text
        assert "Repository" in text
        assert "pytest" in text
        assert "Docker: Yes" in text

    def test_to_human_readable_no_docker(self):
        bp = ProjectBlueprint(project_name="Test", docker=False)
        text = bp.to_human_readable()
        assert "Docker: No" in text

    def test_get_ready_tasks_respects_blueprint_structure(self):
        bp = ProjectBlueprint(
            directory_structure=["src/", "src/models/", "tests/"],
        )
        assert len(bp.directory_structure) == 3

    def test_blueprint_is_frozen(self):
        """ProjectBlueprint must be immutable (frozen=True)."""
        bp = ProjectBlueprint(project_name="Test", backend="FastAPI")
        with pytest.raises((TypeError, ValueError)):
            bp.project_name = "Mutated"


# --- ArchitectAgent Tests ---


class TestArchitectAgent:
    @pytest.mark.asyncio
    async def test_run_no_request(self, architect, base_state):
        base_state["user_request"] = ""
        result = await architect.run(base_state)
        assert result["status"] == "failed"
        assert "No user request" in result["error"]

    @pytest.mark.asyncio
    async def test_run_success(self, architect, base_state):
        blueprint_data = {
            "project_name": "TaskManager",
            "project_type": "web_api",
            "description": "Task management REST API",
            "backend": "FastAPI",
            "backend_language": "python",
            "frontend": "none",
            "frontend_language": "none",
            "database": "PostgreSQL",
            "orm": "SQLAlchemy",
            "cache": "Redis",
            "authentication": "JWT",
            "authorization": "RBAC",
            "api_style": "REST",
            "api_versioning": "url_path",
            "patterns": ["Repository", "Service Layer"],
            "architecture": "layered",
            "directory_structure": [
                "src/",
                "src/models/",
                "src/routes/",
                "src/services/",
                "src/schemas/",
                "tests/",
            ],
            "dependencies": ["fastapi", "sqlalchemy", "pydantic", "uvicorn"],
            "dev_dependencies": ["pytest", "ruff", "mypy", "httpx"],
            "testing": ["pytest", "httpx"],
            "linting": ["ruff"],
            "formatter": ["ruff format"],
            "type_checker": ["mypy"],
            "docker": True,
            "ci_cd": "github_actions",
            "environment_variables": {"DATABASE_URL": "postgresql://localhost/taskdb"},
            "quality_rules": ["All functions must have type hints"],
            "documentation_strategy": "docstrings",
            "coding_conventions": ["PEP 8", "max line length 100"],
            "security_requirements": ["Input validation"],
            "performance_requirements": ["Response time < 200ms"],
            "deployment_target": "docker",
        }

        mock_response = LLMResponse(
            content=json.dumps(blueprint_data),
            model="test-model",
            provider="test-provider",
            tokens_used=150,
        )

        with patch.object(
            architect, "call_llm", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await architect.run(base_state)

        assert result["status"] == "planning"
        assert "project_blueprint" in result
        bp = result["project_blueprint"]
        assert isinstance(bp, ProjectBlueprint)
        assert bp.project_name == "TaskManager"
        assert bp.backend == "FastAPI"
        assert bp.database == "PostgreSQL"
        assert bp.orm == "SQLAlchemy"
        assert bp.authentication == "JWT"
        assert bp.architecture == "layered"
        assert "Repository" in bp.patterns
        assert bp.docker is True

        # Check summary was generated
        assert "blueprint_summary" in result
        assert "TaskManager" in result["blueprint_summary"]

    @pytest.mark.asyncio
    async def test_run_markdown_json(self, architect, base_state):
        blueprint_data = {
            "project_name": "MyApp",
            "project_type": "web_api",
            "description": "Test app",
            "backend": "FastAPI",
            "backend_language": "python",
            "frontend": "none",
            "frontend_language": "none",
            "database": "SQLite",
            "orm": "SQLAlchemy",
            "cache": "none",
            "authentication": "JWT",
            "authorization": "none",
            "api_style": "REST",
            "api_versioning": "none",
            "patterns": [],
            "architecture": "layered",
            "directory_structure": ["src/", "tests/"],
            "dependencies": ["fastapi"],
            "dev_dependencies": ["pytest"],
            "testing": ["pytest"],
            "linting": ["ruff"],
            "formatter": ["ruff format"],
            "type_checker": ["mypy"],
            "docker": False,
            "ci_cd": "none",
            "environment_variables": {},
            "quality_rules": [],
            "documentation_strategy": "docstrings",
            "coding_conventions": [],
            "security_requirements": [],
            "performance_requirements": [],
            "deployment_target": "local",
        }

        mock_response = LLMResponse(
            content=f"```json\n{json.dumps(blueprint_data)}\n```",
            model="test-model",
            provider="test-provider",
            tokens_used=100,
        )

        with patch.object(
            architect, "call_llm", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await architect.run(base_state)

        assert result["status"] == "planning"
        bp = result["project_blueprint"]
        assert bp.project_name == "MyApp"

    @pytest.mark.asyncio
    async def test_run_invalid_json(self, architect, base_state):
        mock_response = LLMResponse(
            content="This is not JSON at all",
            model="test-model",
            provider="test-provider",
            tokens_used=50,
        )

        with patch.object(
            architect, "call_llm", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await architect.run(base_state)

        assert result["status"] == "failed"
        assert "error" in result

    def test_parse_blueprint_basic(self, architect):
        data = {
            "project_name": "Test",
            "project_type": "cli",
            "backend": "none",
            "database": "SQLite",
        }
        bp = architect._parse_blueprint(json.dumps(data))
        assert bp.project_name == "Test"
        assert bp.project_type == "cli"
        assert bp.database == "SQLite"

    def test_parse_blueprint_defaults(self, architect):
        data = {"project_name": "Minimal"}
        bp = architect._parse_blueprint(json.dumps(data))
        assert bp.project_name == "Minimal"
        assert bp.backend == ""
        assert bp.docker is False
        assert bp.patterns == []


# --- Fallback Blueprint Tests ---


class TestFallbackBlueprint:
    def test_fallback_is_valid(self):
        assert isinstance(FALLBACK_BLUEPRINT, ProjectBlueprint)
        assert FALLBACK_BLUEPRINT.project_name == "project"
        assert FALLBACK_BLUEPRINT.backend == "FastAPI"
        assert FALLBACK_BLUEPRINT.database == "PostgreSQL"
