"""Tests for Human-in-the-Loop (HITL) approval flow."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from core.agents.reviewer import ReviewerAgent
from core.orchestrator.state import (
    Severity,
    create_initial_state,
)
from core.schemas import LLMResponse


@pytest.mark.unit
class TestHITLTrigger:
    """Tests for HITL trigger on critical findings."""

    @pytest.mark.asyncio
    async def test_critical_finding_sets_waiting_approval(self) -> None:
        """Critical finding from Reviewer triggers waiting_approval status."""
        agent = ReviewerAgent()
        state = create_initial_state("r1", "Build API with hardcoded password")
        state["generated_code"] = "password = 'secret123'"

        review_json = """{
            "findings": [
                {
                    "id": "sec1",
                    "severity": "critical",
                    "category": "security",
                    "description": "Hardcoded password detected",
                    "suggestion": "Use environment variables"
                }
            ]
        }"""

        agent.call_llm = AsyncMock(
            return_value=LLMResponse(
                content=review_json,
                model="test-model",
                provider="test-provider",
                tokens_used=50,
            )
        )
        result = await agent.run(state)

        assert result["status"] == "waiting_approval"
        assert len(result["review_findings"]) == 1
        assert result["review_findings"][0].severity == Severity.CRITICAL

    @pytest.mark.asyncio
    async def test_multiple_critical_findings(self) -> None:
        """Multiple critical findings still trigger HITL once."""
        agent = ReviewerAgent()
        state = create_initial_state("r1", "Build insecure API")
        state["generated_code"] = "eval(input())"

        review_json = """{
            "findings": [
                {"id": "f1", "severity": "critical",
                 "category": "security", "description": "Code injection"},
                {"id": "f2", "severity": "critical",
                 "category": "security", "description": "XSS vulnerability"}
            ]
        }"""

        agent.call_llm = AsyncMock(
            return_value=LLMResponse(content=review_json, model="t", provider="t", tokens_used=50)
        )
        result = await agent.run(state)

        assert result["status"] == "waiting_approval"
        assert len(result["review_findings"]) == 2


@pytest.mark.unit
class TestApproveEndpoint:
    """Tests for POST /runs/{id}/approve endpoint."""

    @pytest.mark.asyncio
    async def test_approve_requires_auth(self, client: AsyncClient) -> None:
        """Approval endpoint requires authentication."""
        response = await client.post(
            "/api/v1/runs/run-123/approve",
            json={"approved": True},
        )
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_approve_run_success(
        self,
        authenticated_client_with_db: tuple[AsyncClient, AsyncSession],
    ) -> None:
        """Successfully approve a waiting_approval run."""
        client, mock_db = authenticated_client_with_db

        mock_run = MagicMock()
        mock_run.id = "run-123"
        mock_run.status = "waiting_approval"
        mock_run.task_description = "Test task"
        mock_run.generated_code = "code"
        mock_run.tokens_used = 100
        mock_run.created_at = datetime.now(UTC)
        mock_run.updated_at = datetime.now(UTC)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_run
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = await client.post(
            "/api/v1/runs/run-123/approve",
            json={"approved": True, "notes": "Looks safe"},
        )

        assert response.status_code == 200
        assert mock_run.status == "running"

    @pytest.mark.asyncio
    async def test_reject_run(
        self,
        authenticated_client_with_db: tuple[AsyncClient, AsyncSession],
    ) -> None:
        """Reject a waiting_approval run."""
        client, mock_db = authenticated_client_with_db

        mock_run = MagicMock()
        mock_run.id = "run-456"
        mock_run.status = "waiting_approval"
        mock_run.task_description = "Bad task"
        mock_run.generated_code = "bad code"
        mock_run.tokens_used = 50
        mock_run.created_at = datetime.now(UTC)
        mock_run.updated_at = datetime.now(UTC)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_run
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = await client.post(
            "/api/v1/runs/run-456/approve",
            json={"approved": False, "notes": "Security risk"},
        )

        assert response.status_code == 200
        assert mock_run.status == "failed"

    @pytest.mark.asyncio
    async def test_approve_non_waiting_run_fails(
        self,
        authenticated_client_with_db: tuple[AsyncClient, AsyncSession],
    ) -> None:
        """Cannot approve a run that isn't in waiting_approval state."""
        client, mock_db = authenticated_client_with_db

        mock_run = MagicMock()
        mock_run.id = "run-789"
        mock_run.status = "running"
        mock_run.created_at = datetime.now(UTC)
        mock_run.updated_at = datetime.now(UTC)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_run
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = await client.post(
            "/api/v1/runs/run-789/approve",
            json={"approved": True},
        )

        assert response.status_code == 409
