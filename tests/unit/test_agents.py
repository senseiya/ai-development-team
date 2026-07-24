"""Unit tests for all agents with mocked LLM responses."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.agents.coder import CoderAgent
from core.agents.documentation import DocumentationAgent
from core.agents.planner import PlannerAgent
from core.agents.reviewer import ReviewerAgent
from core.agents.tester import TesterAgent
from core.orchestrator.state import (
    AgentState,
    create_initial_state,
)
from core.schemas import LLMResponse, ModelCapability


def _make_state(user_request: str = "Build a REST API") -> AgentState:
    """Create a fresh AgentState for testing."""
    return create_initial_state("test-run-123", user_request)


def _mock_llm_response(content: str, tokens: int = 100) -> LLMResponse:
    """Create a mock LLM response."""
    return LLMResponse(
        content=content,
        model="test-model",
        provider="test-provider",
        tokens_used=tokens,
    )


# --- Planner Agent ---


@pytest.mark.unit
class TestPlannerAgent:
    """Tests for the Planner agent."""

    @pytest.mark.asyncio
    async def test_planner_parses_json_subtasks(self) -> None:
        """Planner correctly parses JSON array of subtasks."""
        agent = PlannerAgent()
        state = _make_state()

        json_response = '''[
            {"id": "1", "title": "Setup", "description": "Init project", "dependencies": []},
            {"id": "2", "title": "Implement", "description": "Write code", "dependencies": ["1"]}
        ]'''

        agent.call_llm = AsyncMock(return_value=_mock_llm_response(json_response))
        result = await agent.run(state)

        assert result["plan"] is not None
        assert len(result["plan"]) == 2
        assert result["plan"][0].id == "1"
        assert result["plan"][0].title == "Setup"
        assert result["plan"][1].dependencies == ["1"]

    @pytest.mark.asyncio
    async def test_planner_handles_markdown_code_block(self) -> None:
        """Planner strips markdown code blocks from LLM response."""
        agent = PlannerAgent()
        state = _make_state()

        json_response = '''```json
[{"id": "1", "title": "Task", "description": "Do stuff", "dependencies": []}]
```'''

        agent.call_llm = AsyncMock(return_value=_mock_llm_response(json_response))
        result = await agent.run(state)

        assert result["plan"] is not None
        assert len(result["plan"]) == 1

    @pytest.mark.asyncio
    async def test_planner_fallback_on_invalid_json(self) -> None:
        """Planner creates fallback subtask on invalid JSON."""
        agent = PlannerAgent()
        state = _make_state()

        agent.call_llm = AsyncMock(return_value=_mock_llm_response("not json at all"))
        result = await agent.run(state)

        assert result["plan"] is not None
        assert len(result["plan"]) == 1
        assert result["plan"][0].title == "Execute request"

    @pytest.mark.asyncio
    async def test_planner_empty_request(self) -> None:
        """Planner fails gracefully on empty request."""
        agent = PlannerAgent()
        state = _make_state("")
        result = await agent.run(state)

        assert result["status"] == "failed"
        assert "No user request" in (result.get("error") or "")


# --- Coder Agent ---


@pytest.mark.unit
class TestCoderAgent:
    """Tests for the Coder agent."""

    @pytest.mark.asyncio
    async def test_coder_generates_code(self) -> None:
        """Coder generates code from user request."""
        agent = CoderAgent()
        state = _make_state("Create a hello world function")

        agent.call_llm = AsyncMock(
            return_value=_mock_llm_response("def hello(): print('Hello')")
        )
        result = await agent.run(state)

        assert result["generated_code"] == "def hello(): print('Hello')"
        assert result["status"] == "completed"
        assert result["tokens_used"] == 100

    @pytest.mark.asyncio
    async def test_coder_empty_request(self) -> None:
        """Coder fails on empty request."""
        agent = CoderAgent()
        state = _make_state("")
        result = await agent.run(state)

        assert result["status"] == "failed"

    @pytest.mark.asyncio
    async def test_coder_capability_is_code_generation(self) -> None:
        """Coder declares CODE_GENERATION capability."""
        agent = CoderAgent()
        assert agent.capability == ModelCapability.CODE_GENERATION


# --- Tester Agent ---


@pytest.mark.unit
class TestTesterAgent:
    """Tests for the Tester agent."""

    @pytest.mark.asyncio
    async def test_tester_analyzes_code(self) -> None:
        """Tester produces test report from generated code."""
        agent = TesterAgent()
        state = _make_state()
        state["generated_code"] = "def hello(): return 'world'"

        test_json = '''{
            "total": 2,
            "passed": 1,
            "failed": 1,
            "results": [
                {"test_name": "test_hello", "passed": true, "output": "OK"},
                {"test_name": "test_error", "passed": false, "output": "Failed"}
            ],
            "summary": "1 failing test"
        }'''

        agent.call_llm = AsyncMock(return_value=_mock_llm_response(test_json))
        result = await agent.run(state)

        assert result["test_results"] is not None
        assert result["test_results"].total == 2
        assert result["test_results"].passed == 1
        assert result["test_results"].failed == 1
        assert result["iteration_count"] == 1

    @pytest.mark.asyncio
    async def test_tester_no_code(self) -> None:
        """Tester handles missing code gracefully."""
        agent = TesterAgent()
        state = _make_state()
        # No generated_code in state
        result = await agent.run(state)

        assert result["test_results"] is not None
        assert result["test_results"].failed == 1
        assert result["iteration_count"] == 1

    @pytest.mark.asyncio
    async def test_tester_increments_iteration(self) -> None:
        """Tester increments iteration_count."""
        agent = TesterAgent()
        state = _make_state()
        state["generated_code"] = "x = 1"
        state["iteration_count"] = 2

        agent.call_llm = AsyncMock(
            return_value=_mock_llm_response('{"total": 1, "passed": 1, "failed": 0, "results": []}')
        )
        result = await agent.run(state)

        assert result["iteration_count"] == 3


# --- Reviewer Agent ---


@pytest.mark.unit
class TestReviewerAgent:
    """Tests for the Reviewer agent."""

    @pytest.mark.asyncio
    async def test_reviewer_finds_issues(self) -> None:
        """Reviewer produces findings from code review."""
        agent = ReviewerAgent()
        state = _make_state()
        state["generated_code"] = "password = 'hardcoded'"

        review_json = '''{
            "findings": [
                {
                    "id": "f1",
                    "severity": "critical",
                    "category": "security",
                    "description": "Hardcoded password",
                    "suggestion": "Use environment variables"
                }
            ],
            "summary": "Critical security issue found"
        }'''

        agent.call_llm = AsyncMock(return_value=_mock_llm_response(review_json))
        result = await agent.run(state)

        assert len(result["review_findings"]) == 1
        assert result["review_findings"][0].severity.value == "critical"
        assert result["review_findings"][0].category == "security"
        # Critical finding triggers HITL
        assert result["status"] == "waiting_approval"

    @pytest.mark.asyncio
    async def test_reviewer_no_critical(self) -> None:
        """Reviewer without critical findings doesn't trigger HITL."""
        agent = ReviewerAgent()
        state = _make_state()
        state["generated_code"] = "x = 1"

        review_json = '''{
            "findings": [
                {
                    "id": "f1",
                    "severity": "info",
                    "category": "style",
                    "description": "Consider adding docstring"
                }
            ]
        }'''

        agent.call_llm = AsyncMock(return_value=_mock_llm_response(review_json))
        result = await agent.run(state)

        assert result["status"] != "waiting_approval"
        assert len(result["review_findings"]) == 1

    @pytest.mark.asyncio
    async def test_reviewer_no_code(self) -> None:
        """Reviewer handles missing code gracefully."""
        agent = ReviewerAgent()
        state = _make_state()
        result = await agent.run(state)

        assert len(result["review_findings"]) == 1
        assert result["review_findings"][0].severity.value == "warning"


# --- Documentation Agent ---


@pytest.mark.unit
class TestDocumentationAgent:
    """Tests for the Documentation agent."""

    @pytest.mark.asyncio
    async def test_documentation_generates_docs(self) -> None:
        """Documentation agent produces documentation from code."""
        agent = DocumentationAgent()
        state = _make_state()
        state["generated_code"] = "def hello(): return 'world'"

        agent.call_llm = AsyncMock(
            return_value=_mock_llm_response("# Hello Function\nReturns 'world'")
        )
        result = await agent.run(state)

        assert result["documentation"] == "# Hello Function\nReturns 'world'"
        assert result["status"] == "documenting"

    @pytest.mark.asyncio
    async def test_documentation_no_code(self) -> None:
        """Documentation agent handles missing code."""
        agent = DocumentationAgent()
        state = _make_state()
        result = await agent.run(state)

        assert "No code" in result["documentation"]
