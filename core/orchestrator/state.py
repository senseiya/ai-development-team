"""Shared state types for the multi-agent orchestration graph.

AgentState is the TypedDict that flows through the LangGraph StateGraph.
Every agent reads from and writes to this state. The checkpointer persists
it to run_checkpoints on each graph transition.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Literal, TypedDict


# --- Enums ---


class RunStatus(str, Enum):
    """Status of a development run."""

    PLANNING = "planning"
    CODING = "coding"
    TESTING = "testing"
    REVIEWING = "reviewing"
    DOCUMENTING = "documenting"
    DONE = "done"
    FAILED = "failed"
    WAITING_APPROVAL = "waiting_approval"


class Severity(str, Enum):
    """Severity level for review findings."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


# --- Dataclasses for structured state fields ---


@dataclass
class SubTask:
    """A single subtask produced by the Planner agent."""

    id: str
    title: str
    description: str
    dependencies: list[str] = field(default_factory=list)
    status: str = "pending"


@dataclass
class FileDiff:
    """A file change produced during the coding phase."""

    file_path: str
    action: str  # "create", "modify", "delete"
    content: str = ""
    diff: str = ""


@dataclass
class TestResult:
    """Result of a single test case."""

    test_name: str
    passed: bool
    output: str = ""
    duration_ms: float = 0.0


@dataclass
class TestSuiteReport:
    """Aggregated test results from the Tester agent."""

    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    results: list[TestResult] = field(default_factory=list)
    output: str = ""
    duration_ms: float = 0.0


@dataclass
class ReviewFinding:
    """A finding from the Reviewer agent."""

    id: str
    severity: Severity
    category: str  # "security", "performance", "style", "bug", "logic"
    file_path: str | None = None
    line_number: int | None = None
    description: str = ""
    suggestion: str = ""


@dataclass
class AgentMessage:
    """A message exchanged between agents during a run."""

    agent_name: str
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    message_type: str = "info"  # "info", "warning", "error", "decision"


# --- Main state TypedDict ---


class AgentState(TypedDict, total=False):
    """Shared state flowing through the LangGraph orchestration graph.

    Every agent reads relevant fields and writes its outputs back.
    The checkpointer persists this on each graph transition.
    """

    run_id: str
    user_request: str
    plan: list[SubTask] | None
    current_step: str
    files_changed: list[FileDiff]
    test_results: TestSuiteReport | None
    review_findings: list[ReviewFinding]
    documentation: str | None
    iteration_count: int
    status: Literal[
        "planning",
        "coding",
        "testing",
        "reviewing",
        "documenting",
        "done",
        "failed",
        "waiting_approval",
    ]
    messages: list[AgentMessage]
    cost_usd: float
    tokens_used: int
    router: object | None
    error: str | None
    # Phase 5: workspace and tool execution state
    workspace_path: str
    model_used: str
    provider_used: str
    sandbox_exit_code: int
    sandbox_output: str
    pr_url: str
    github_owner: str
    github_repo: str


def create_initial_state(
    run_id: str,
    user_request: str,
    router: object | None = None,
) -> AgentState:
    """Create a fresh AgentState for a new run.

    Args:
        run_id: Unique identifier for this run.
        user_request: The user's natural language request.
        router: Optional ModelRouter instance.

    Returns:
        Initialized AgentState with default values.
    """
    return AgentState(
        run_id=run_id,
        user_request=user_request,
        plan=None,
        current_step="planning",
        files_changed=[],
        test_results=None,
        review_findings=[],
        documentation=None,
        iteration_count=0,
        status="planning",
        messages=[],
        cost_usd=0.0,
        tokens_used=0,
        router=router,
        error=None,
    )
