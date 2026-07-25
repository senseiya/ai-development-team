"""Shared state types for the multi-agent orchestration graph.

AgentState is the TypedDict that flows through the LangGraph StateGraph.
Every agent reads from and writes to this state. The checkpointer persists
it to run_checkpoints on each graph transition.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field

# --- Enums ---


class RunStatus(StrEnum):
    """Estado público/de negocio de un Run completo.

    Es el estado que ve el cliente y que vive en la tabla runs.
    Se deriva del estado interno (AgentState.status) en un solo
    lugar (graph.py), nunca se actualiza independientemente.
    """

    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class Severity(StrEnum):
    """Severity level for review findings."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class FileStatus(StrEnum):
    """Status of a file generation task."""

    PENDING = "pending"
    GENERATING = "generating"
    VALIDATING = "validating"
    REPAIRING = "repairing"
    FAILED = "failed"
    DONE = "done"


class BlueprintDecision(BaseModel):
    """A single architectural decision recorded by the Architect.

    Each entry records what was chosen, why, and what alternatives
    were considered. Used by Reviewer, Documentation, and future
    Evaluator agents.
    """

    category: str
    selected: str
    rationale: str
    alternatives: list[str] = Field(default_factory=list)


class ProjectBlueprint(BaseModel):
    """Complete architectural blueprint for a project.

    Produced by the ArchitectAgent. Every downstream agent reads
    this to stay consistent — no agent should make architectural
    decisions; they all follow this blueprint.

    Immutable after creation (frozen=True). The only way to obtain
    a different blueprint is to start a new Run.
    """

    model_config = ConfigDict(frozen=True, use_enum_values=True)

    # Versioning — never break compatibility
    blueprint_version: int = Field(default=1, ge=1)
    schema_version: int = Field(default=1, ge=1)

    # Identity
    project_name: str = ""
    project_type: Literal["web_api", "cli", "library", "fullstack", "microservice"] = "web_api"
    description: str = ""

    # Backend
    backend: str = ""  # validated against blueprint_options table
    backend_language: Literal["python", "typescript", "go", "rust", "javascript"] = "python"

    # Frontend
    frontend: str = ""  # validated against blueprint_options table
    frontend_language: Literal["typescript", "javascript", "none"] = "none"

    # Data layer
    database: str = "none"  # validated against blueprint_options table
    orm: str = "none"  # validated against blueprint_options table
    cache: str = "none"

    # Auth
    authentication: str = ""  # validated against blueprint_options table
    authorization: Literal["RBAC", "simple_role", "none"] = "none"

    # API style
    api_style: Literal["REST", "GraphQL", "gRPC", "none"] = "REST"
    api_versioning: Literal["url_path", "header", "none"] = "none"

    # Patterns
    patterns: list[str] = Field(default_factory=list)
    architecture: Literal["layered", "hexagonal", "clean", "modular", "monolith"] = "layered"

    # Project structure
    directory_structure: list[str] = Field(default_factory=list)

    # Dependencies
    dependencies: list[str] = Field(default_factory=list)
    dev_dependencies: list[str] = Field(default_factory=list)

    # Quality tooling
    testing: list[str] = Field(default_factory=list)
    linting: list[str] = Field(default_factory=list)
    formatter: list[str] = Field(default_factory=list)
    type_checker: list[str] = Field(default_factory=list)

    # Infrastructure
    docker: bool = False
    ci_cd: str = "none"
    environment_variables: dict[str, str] = Field(default_factory=dict)

    # Quality rules
    quality_rules: list[str] = Field(default_factory=list)
    documentation_strategy: str = "docstrings"
    coding_conventions: list[str] = Field(default_factory=list)

    # Requirements
    security_requirements: list[str] = Field(default_factory=list)
    performance_requirements: list[str] = Field(default_factory=list)
    deployment_target: Literal["local", "docker", "aws", "gcp", "railway", "render"] = "docker"

    # Architectural decisions (why each choice was made)
    decisions: list[BlueprintDecision] = Field(default_factory=list)

    def to_human_readable(self) -> str:
        """Generate a human-readable technical summary of the blueprint."""
        sections = [
            f"=== {self.project_name} ===",
            f"Type: {self.project_type}",
            f"Description: {self.description}",
            "",
            "--- Backend ---",
            f"Framework: {self.backend}",
            f"Language: {self.backend_language}",
            f"API Style: {self.api_style}",
            "",
            "--- Frontend ---",
            f"Framework: {self.frontend}",
            f"Language: {self.frontend_language}",
            "",
            "--- Data ---",
            f"Database: {self.database}",
            f"ORM: {self.orm}",
            f"Cache: {self.cache}",
            "",
            "--- Auth ---",
            f"Authentication: {self.authentication}",
            f"Authorization: {self.authorization}",
            "",
            "--- Architecture ---",
            f"Pattern: {self.architecture}",
            f"Patterns: {', '.join(self.patterns)}",
            "",
            "--- Structure ---",
            *[f"  {d}" for d in self.directory_structure],
            "",
            "--- Quality ---",
            f"Testing: {', '.join(self.testing)}",
            f"Linting: {', '.join(self.linting)}",
            f"Formatting: {', '.join(self.formatter)}",
            f"Type Checking: {', '.join(self.type_checker)}",
            "",
            "--- Infrastructure ---",
            f"Docker: {'Yes' if self.docker else 'No'}",
            f"CI/CD: {self.ci_cd}",
            f"Deployment: {self.deployment_target}",
        ]

        if self.dependencies:
            sections.extend(["", "--- Dependencies ---", *[f"  {d}" for d in self.dependencies]])

        if self.coding_conventions:
            sections.extend([
                "",
                "--- Conventions ---",
                *[f"  {c}" for c in self.coding_conventions],
            ])

        if self.decisions:
            sections.extend(["", "--- Decisions ---"])
            for d in self.decisions:
                sections.append(f"  {d.category}: {d.selected}")
                sections.append(f"    Why: {d.rationale}")
                if d.alternatives:
                    sections.append(f"    Alternatives: {', '.join(d.alternatives)}")

        return "\n".join(sections)


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


@dataclass
class FileTask:
    """A single file to be generated by the Coder agent."""

    file_path: str
    description: str
    dependencies: list[str] = field(default_factory=list)
    status: FileStatus = FileStatus.PENDING
    content: str = ""
    error: str | None = None
    repair_attempts: int = 0


@dataclass
class ProjectPlan:
    """Complete project decomposition into file-level tasks."""

    files: list[FileTask] = field(default_factory=list)
    project_name: str = ""
    project_description: str = ""

    def get_ready_tasks(self) -> list[FileTask]:
        """Get tasks whose dependencies are all DONE."""
        done_paths = {t.file_path for t in self.files if t.status == FileStatus.DONE}
        return [
            t
            for t in self.files
            if t.status == FileStatus.PENDING
            and all(dep in done_paths for dep in t.dependencies)
        ]

    def get_task(self, file_path: str) -> FileTask | None:
        """Get task by file path."""
        for task in self.files:
            if task.file_path == file_path:
                return task
        return None

    def all_done(self) -> bool:
        """Check if all tasks completed successfully."""
        return all(t.status == FileStatus.DONE for t in self.files)

    def has_failures(self) -> bool:
        """Check if any tasks failed permanently."""
        return any(t.status == FileStatus.FAILED for t in self.files)

    def total_tokens(self) -> int:
        """Count total files."""
        return len(self.files)


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
    # Estado interno del pipeline (qué nodo del grafo está ejecutando)
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
    # Estado público/de negocio del Run (derivado de status en graph.py)
    run_status: str | None
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
    # Incremental generation fields
    file_tasks: list[FileTask]
    project_plan: ProjectPlan | None
    current_file_index: int
    generated_files: list[str]
    validation_errors: dict[str, str]
    # Architect phase
    project_blueprint: ProjectBlueprint | None
    blueprint_summary: str


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
        file_tasks=[],
        project_plan=None,
        current_file_index=0,
        generated_files=[],
        validation_errors={},
        project_blueprint=None,
        blueprint_summary="",
        run_status="pending",
    )
