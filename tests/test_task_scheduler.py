"""Tests for TaskScheduler agent."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from core.agents.task_scheduler import TaskScheduler
from core.orchestrator.state import (
    AgentState,
    FileStatus,
    FileTask,
    ProjectPlan,
    create_initial_state,
)
from core.schemas import LLMResponse


@pytest.fixture
def scheduler() -> TaskScheduler:
    return TaskScheduler()


@pytest.fixture
def base_state() -> AgentState:
    return create_initial_state(run_id="test-123", user_request="Build a simple calculator")


class TestFileTask:
    def test_file_task_defaults(self):
        task = FileTask(file_path="src/main.py", description="Main entry point")
        assert task.status == FileStatus.PENDING
        assert task.dependencies == []
        assert task.repair_attempts == 0
        assert task.content == ""
        assert task.error is None


class TestProjectPlan:
    def test_get_ready_tasks_no_deps(self):
        plan = ProjectPlan(
            files=[
                FileTask(file_path="a.py", description="A"),
                FileTask(file_path="b.py", description="B"),
            ]
        )
        ready = plan.get_ready_tasks()
        assert len(ready) == 2

    def test_get_ready_tasks_with_deps(self):
        plan = ProjectPlan(
            files=[
                FileTask(file_path="base.py", description="Base"),
                FileTask(file_path="app.py", description="App", dependencies=["base.py"]),
            ]
        )
        ready = plan.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].file_path == "base.py"

    def test_get_ready_tasks_dep_done(self):
        plan = ProjectPlan(
            files=[
                FileTask(file_path="base.py", description="Base", status=FileStatus.DONE),
                FileTask(file_path="app.py", description="App", dependencies=["base.py"]),
            ]
        )
        ready = plan.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].file_path == "app.py"

    def test_all_done(self):
        plan = ProjectPlan(
            files=[
                FileTask(file_path="a.py", description="A", status=FileStatus.DONE),
                FileTask(file_path="b.py", description="B", status=FileStatus.DONE),
            ]
        )
        assert plan.all_done() is True

    def test_all_done_partial(self):
        plan = ProjectPlan(
            files=[
                FileTask(file_path="a.py", description="A", status=FileStatus.DONE),
                FileTask(file_path="b.py", description="B", status=FileStatus.PENDING),
            ]
        )
        assert plan.all_done() is False

    def test_has_failures(self):
        plan = ProjectPlan(
            files=[
                FileTask(file_path="a.py", description="A", status=FileStatus.FAILED),
            ]
        )
        assert plan.has_failures() is True

    def test_get_task(self):
        plan = ProjectPlan(
            files=[FileTask(file_path="a.py", description="A")]
        )
        task = plan.get_task("a.py")
        assert task is not None
        assert task.file_path == "a.py"

    def test_get_task_not_found(self):
        plan = ProjectPlan(
            files=[FileTask(file_path="a.py", description="A")]
        )
        task = plan.get_task("b.py")
        assert task is None


class TestTaskScheduler:
    @pytest.mark.asyncio
    async def test_run_no_request(self, scheduler, base_state):
        base_state["user_request"] = ""
        result = await scheduler.run(base_state)
        assert result["status"] == "failed"
        assert "No user request" in result["error"]

    @pytest.mark.asyncio
    async def test_run_success(self, scheduler, base_state):
        mock_response = LLMResponse(
            content=json.dumps(
                {
                    "project_name": "calculator",
                    "project_description": "Simple calculator",
                    "files": [
                        {
                            "file_path": "src/main.py",
                            "description": "Entry point",
                            "dependencies": [],
                        },
                        {
                            "file_path": "src/calc.py",
                            "description": "Calculator",
                            "dependencies": [],
                        },
                    ],
                }
            ),
            model="test-model",
            provider="test-provider",
            tokens_used=100,
        )

        with patch.object(
            scheduler, "call_llm", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await scheduler.run(base_state)

        assert result["status"] == "planning"
        assert "project_plan" in result
        plan = result["project_plan"]
        assert plan.project_name == "calculator"
        assert len(plan.files) == 2

    @pytest.mark.asyncio
    async def test_run_json_error(self, scheduler, base_state):
        mock_response = LLMResponse(
            content="This is not JSON",
            model="test-model",
            provider="test-provider",
            tokens_used=50,
        )

        with patch.object(
            scheduler, "call_llm", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await scheduler.run(base_state)

        assert result["status"] == "failed"

    def test_parse_plan_markdown(self, scheduler):
        content = """```json
{
  "project_name": "test",
  "project_description": "test project",
  "files": [{"file_path": "a.py", "description": "A", "dependencies": []}]
}
```"""
        plan = scheduler._parse_plan(content)
        assert plan.project_name == "test"
        assert len(plan.files) == 1
