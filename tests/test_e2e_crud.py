"""End-to-end pipeline test: CRUD with UI via mocked LLM.

Simulates the full pipeline:
  architect → planner → generate_file* → tester → reviewer → documentation

Uses mocked LLM responses so no real API calls are made.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from core.agents.architect import ArchitectAgent
from core.agents.coder import CoderAgent
from core.agents.context_builder import ContextBuilder
from core.agents.planner import PlannerAgent
from core.agents.syntax_validator import SyntaxValidator
from core.orchestrator.state import (
    AgentState,
    FileStatus,
    ProjectBlueprint,
    ProjectPlan,
    create_initial_state,
)
from core.schemas import LLMResponse

# --- Fixtures ---


@pytest.fixture
def state() -> AgentState:
    return create_initial_state(
        run_id="e2e-crud-001",
        user_request="Create a simple task CRUD with FastAPI, SQLite, and an HTML UI",
    )


# --- Mock data ---

BLUEPRINT_RESPONSE = {
    "project_name": "TaskCRUD",
    "project_type": "fullstack",
    "description": "Simple task CRUD with FastAPI backend and HTML UI",
    "backend": "FastAPI",
    "backend_language": "python",
    "frontend": "HTML+CSS",
    "frontend_language": "none",
    "database": "SQLite",
    "orm": "SQLAlchemy",
    "cache": "none",
    "authentication": "none",
    "authorization": "none",
    "api_style": "REST",
    "api_versioning": "none",
    "patterns": ["Repository"],
    "architecture": "layered",
    "directory_structure": [
        "src/",
        "src/models/",
        "src/routes/",
        "src/services/",
        "src/schemas/",
        "src/templates/",
        "tests/",
    ],
    "dependencies": ["fastapi", "sqlalchemy", "pydantic", "uvicorn", "jinja2"],
    "dev_dependencies": ["pytest", "ruff", "httpx"],
    "testing": ["pytest", "httpx"],
    "linting": ["ruff"],
    "formatter": ["ruff format"],
    "type_checker": [],
    "docker": False,
    "ci_cd": "none",
    "environment_variables": {},
    "quality_rules": ["All functions must have type hints"],
    "documentation_strategy": "docstrings",
    "coding_conventions": ["PEP 8"],
    "security_requirements": [],
    "performance_requirements": [],
    "deployment_target": "local",
}

PLANNER_RESPONSE = {
    "files": [
        {
            "file_path": "pyproject.toml",
            "description": "Project config with dependencies",
            "dependencies": [],
        },
        {
            "file_path": "src/__init__.py",
            "description": "Package init",
            "dependencies": [],
        },
        {
            "file_path": "src/models/task.py",
            "description": "Task SQLAlchemy model",
            "dependencies": ["pyproject.toml"],
        },
        {
            "file_path": "src/schemas/task.py",
            "description": "Pydantic schemas for Task",
            "dependencies": ["src/models/task.py"],
        },
        {
            "file_path": "src/services/task_service.py",
            "description": "Business logic for Task CRUD",
            "dependencies": ["src/models/task.py", "src/schemas/task.py"],
        },
        {
            "file_path": "src/routes/tasks.py",
            "description": "FastAPI routes for Task CRUD",
            "dependencies": ["src/services/task_service.py"],
        },
        {
            "file_path": "src/main.py",
            "description": "FastAPI app entry point",
            "dependencies": ["src/routes/tasks.py", "src/templates/"],
        },
        {
            "file_path": "tests/test_tasks.py",
            "description": "Tests for task CRUD endpoints",
            "dependencies": ["src/main.py"],
        },
    ]
}

CODER_RESPONSE = """from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(String(1000), default="")
    completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
"""


# --- Test: Full pipeline with mocked LLM ---


@pytest.mark.asyncio
async def test_architect_creates_blueprint(state: AgentState):
    """ArchitectAgent produces a valid ProjectBlueprint."""
    agent = ArchitectAgent()
    agent.call_llm = AsyncMock(
        return_value=LLMResponse(
            content=json.dumps(BLUEPRINT_RESPONSE),
            model="test-model",
            provider="test-provider",
            tokens_used=200,
        )
    )
    result = await agent.run(state)

    assert result["status"] == "planning"
    bp = result.get("project_blueprint")
    assert bp is not None
    assert isinstance(bp, ProjectBlueprint)
    assert bp.project_name == "TaskCRUD"
    assert bp.backend == "FastAPI"
    assert bp.database == "SQLite"
    assert "Repository" in bp.patterns
    assert "jinja2" in bp.dependencies
    assert "tests/" in bp.directory_structure

    summary = result.get("blueprint_summary", "")
    assert "TaskCRUD" in summary
    assert "FastAPI" in summary
    assert "SQLite" in summary


@pytest.mark.asyncio
async def test_planner_uses_blueprint(state: AgentState):
    """Planner reads blueprint and delegates to TaskScheduler."""
    # Set blueprint
    from core.orchestrator.state import ProjectBlueprint

    blueprint = ProjectBlueprint(**BLUEPRINT_RESPONSE)
    state["project_blueprint"] = blueprint

    agent = PlannerAgent()
    agent._scheduler.call_llm = AsyncMock(
        return_value=LLMResponse(
            content=json.dumps(PLANNER_RESPONSE),
            model="test-model",
            provider="test-provider",
            tokens_used=150,
        )
    )
    result = await agent.run(state)

    assert result["status"] == "planning"
    project_plan = result.get("project_plan")
    assert project_plan is not None
    assert isinstance(project_plan, ProjectPlan)
    assert len(project_plan.files) == 8
    assert project_plan.files[0].file_path == "pyproject.toml"
    assert project_plan.files[6].file_path == "src/main.py"
    assert result.get("plan") is not None  # legacy subtasks


@pytest.mark.asyncio
async def test_coder_generates_single_file(state: AgentState):
    """CoderAgent generates one file with raw content."""
    blueprint = ProjectBlueprint(**BLUEPRINT_RESPONSE)
    state["project_blueprint"] = blueprint

    project_plan = ProjectPlan(
        project_name="TaskCRUD",
        files=[
            # Only need one task for this test
            type(
                "FileTask",
                (),
                {
                    "file_path": "src/models/task.py",
                    "description": "Task SQLAlchemy model",
                    "dependencies": [],
                    "status": type("Status", (), {"value": "done"})(),
                    "content": "",
                },
            )
        ],
    )

    coder = CoderAgent()
    file_task = project_plan.files[0]
    context_builder = ContextBuilder(project_plan, blueprint)

    coder.call_llm = AsyncMock(
        return_value=LLMResponse(
            content=CODER_RESPONSE,
            model="test-model",
            provider="test-provider",
            tokens_used=100,
        )
    )

    content = await coder.generate_file(file_task, context_builder, state)
    assert content is not None
    assert "class Task" in content
    assert "sqlalchemy" in content.lower()
    assert "Column" in content
    assert "Integer" in content


@pytest.mark.asyncio
async def test_full_pipeline_mocked(state: AgentState):
    """End-to-end test: architect → planner → coder → validate."""
    # Step 1: Architect
    architect = ArchitectAgent()
    architect.call_llm = AsyncMock(
        return_value=LLMResponse(
            content=json.dumps(BLUEPRINT_RESPONSE),
            model="test",
            provider="test",
            tokens_used=200,
        )
    )
    state = await architect.run(state)
    assert state["project_blueprint"] is not None
    blueprint: ProjectBlueprint = state["project_blueprint"]

    # Step 2: Planner
    planner = PlannerAgent()
    planner._scheduler.call_llm = AsyncMock(
        return_value=LLMResponse(
            content=json.dumps(PLANNER_RESPONSE),
            model="test",
            provider="test",
            tokens_used=150,
        )
    )
    state = await planner.run(state)
    assert state["project_plan"] is not None
    project_plan: ProjectPlan = state["project_plan"]

    # Step 3: Generate first file and validate
    ready = project_plan.get_ready_tasks()
    assert len(ready) >= 1

    coder = CoderAgent()
    context_builder = ContextBuilder(project_plan, blueprint)
    validator = SyntaxValidator()

    file_task = ready[0]  # pyproject.toml
    file_task.status = FileStatus.GENERATING

    # Coder will be called for each file; mock it
    coder.call_llm = AsyncMock(
        return_value=LLMResponse(
            content=CODER_RESPONSE,
            model="test",
            provider="test",
            tokens_used=100,
        )
    )
    content = await coder.generate_file(file_task, context_builder, state)
    assert content is not None

    # Validate
    validation = validator.validate(file_task.file_path, content)
    assert validation.is_valid is True

    file_task.status = FileStatus.DONE
    file_task.content = content

    # Verify the project has 8 files total
    assert len(project_plan.files) == 8

    # Verify dependencies are correct
    src_routes = project_plan.get_task("src/routes/tasks.py")
    assert src_routes is not None
    assert "src/services/task_service.py" in src_routes.dependencies
