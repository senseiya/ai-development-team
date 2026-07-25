"""LangGraph StateGraph for the multi-agent orchestration.

Defines the complete agent pipeline with incremental file generation:
  architect → planner → (file generation loop) → tester → reviewer → documentation → done

With conditional edges:
  - file loop: generate → validate → repair? → next file
  - tester → generate_file (if tests fail AND iteration_count < MAX_ITERATIONS)
  - reviewer → END (if severity=critical → waiting_approval)
  - any node → failed (on unhandled exception)

Phase 7: Each node is instrumented with AgentTracer for Prometheus metrics.
Phase 9: Incremental file-by-file generation with syntax validation.
Phase 10: ArchitectAgent produces ProjectBlueprint before any code decisions.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Literal

from langgraph.graph import END, StateGraph

from core.agents.architect import ArchitectAgent
from core.agents.artifact_manager import ArtifactManager
from core.agents.coder import CoderAgent
from core.agents.context_builder import ContextBuilder
from core.agents.documentation import DocumentationAgent
from core.agents.planner import PlannerAgent
from core.agents.repair_agent import RepairAgent
from core.agents.reviewer import ReviewerAgent
from core.agents.syntax_validator import SyntaxValidator
from core.agents.tester import TesterAgent
from core.observability.tracing import AgentTracer
from core.orchestrator.state import AgentMessage, AgentState, FileStatus, ProjectPlan, RunStatus
from core.validators.blueprint_validator import BlueprintValidationError, BlueprintValidator

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 3
MAX_REPAIR_ATTEMPTS = 3
MAX_FILE_RETRIES = 3
FILE_RETRY_BACKOFF_BASE = 2.0  # seconds: 2, 4, 8


def derive_run_status(state: AgentState) -> str:
    """Derive the public RunStatus from the internal AgentState.

    Se ejecuta en cada nodo del grafo para mantener sincronizado
    el estado público del Run con el estado interno del pipeline.

    Reglas:
      - AgentState.status == "failed"          → RunStatus.FAILED
      - AgentState.status == "waiting_approval" → RunStatus.WAITING_APPROVAL
      - AgentState.status == "done" + sin errores de archivos → RunStatus.COMPLETED
      - AgentState.status == "done" + archivos fallidos → RunStatus.PARTIAL_SUCCESS
      - pipeline en ejecución → RunStatus.RUNNING
    """
    internal_status = state.get("status", "")

    # Terminal states
    if internal_status == "failed":
        return RunStatus.FAILED.value
    if internal_status == "waiting_approval":
        return RunStatus.WAITING_APPROVAL.value
    if internal_status == "done":
        # Check for failed files
        project_plan = state.get("project_plan")
        if project_plan and hasattr(project_plan, "has_failures") and project_plan.has_failures():
                return RunStatus.PARTIAL_SUCCESS.value
        return RunStatus.COMPLETED.value

    # Running (non-terminal state)
    return RunStatus.RUNNING.value


async def _architect_node(state: AgentState) -> AgentState:
    """Run the Architect agent with tracing and blueprint validation."""
    agent = ArchitectAgent()
    run_id = state.get("run_id", "")
    with AgentTracer("architect", run_id) as tracer:
        result = await agent.run(state)
        tracer.record_tokens(
            result.get("tokens_used", 0),
            result.get("provider_used", ""),
            result.get("model_used", ""),
        )
        # Validate blueprint architectural compatibility
        blueprint = result.get("project_blueprint")
        if blueprint and result.get("status") != "failed":
            try:
                validator = BlueprintValidator()
                validator.validate(blueprint)
            except BlueprintValidationError as e:
                logger.error("Blueprint validation failed: %s", e)
                result["status"] = "failed"
                result["error"] = str(e)
                result.setdefault("messages", []).append(
                    AgentMessage(
                        agent_name="architect",
                        content=str(e),
                        message_type="error",
                    )
                )
        result["run_status"] = derive_run_status(result)
        return result


async def _planner_node(state: AgentState) -> AgentState:
    """Run the Planner agent with tracing."""
    agent = PlannerAgent()
    run_id = state.get("run_id", "")
    with AgentTracer("planner", run_id) as tracer:
        result = await agent.run(state)
        tracer.record_tokens(
            result.get("tokens_used", 0),
            result.get("provider_used", ""),
            result.get("model_used", ""),
        )
        result["run_status"] = derive_run_status(result)
        return result


async def _generate_file_node(state: AgentState) -> AgentState:
    """Generate a single file with validation and repair loop."""
    project_plan = state.get("project_plan")
    if not project_plan or not isinstance(project_plan, ProjectPlan):
        state["status"] = "failed"
        state["error"] = "No project plan available"
        state["run_status"] = derive_run_status(state)
        return state

    workspace_path = state.get("workspace_path", "")
    artifact_mgr = ArtifactManager(workspace_path) if workspace_path else None
    blueprint = state.get("project_blueprint")
    context_builder = ContextBuilder(project_plan, blueprint)
    validator = SyntaxValidator()
    repair_agent = RepairAgent()
    coder = CoderAgent()

    # Find next file to generate
    ready_tasks = project_plan.get_ready_tasks()
    if not ready_tasks:
        if project_plan.all_done():
            state["status"] = "done"
            state["current_file_index"] = len(project_plan.files)
        elif project_plan.has_failures():
            state["status"] = "failed"
            state["error"] = "Some files failed to generate"
        state["run_status"] = derive_run_status(state)
        return state

    file_task = ready_tasks[0]
    file_task.status = FileStatus.GENERATING

    # Generate the file (with retry + backoff on provider errors)
    content = await coder.generate_file(file_task, context_builder, state)

    if content is None:
        logger.warning(
            "Provider error for %s, retrying with backoff (max %d)",
            file_task.file_path, MAX_FILE_RETRIES,
        )
        for attempt in range(1, MAX_FILE_RETRIES + 1):
            wait = FILE_RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
            logger.info(
                "Retry %d/%d for %s after %.1fs",
                attempt, MAX_FILE_RETRIES, file_task.file_path, wait,
            )
            await asyncio.sleep(wait)
            content = await coder.generate_file(file_task, context_builder, state)
            if content is not None:
                logger.info("Retry %d succeeded for %s", attempt, file_task.file_path)
                break

    if content is None:
        file_task.status = FileStatus.FAILED
        file_task.error = "Generation failed after retries"
        if artifact_mgr:
            artifact_mgr.save_generation_log(
                file_task.file_path, "generate", False, "Generation failed after retries"
            )
        state["status"] = "failed"
        state["error"] = (
                f"Failed to generate {file_task.file_path} "
                f"after {MAX_FILE_RETRIES} retries"
            )
        state["run_status"] = derive_run_status(state)
        return state

    # Validate syntax
    file_task.status = FileStatus.VALIDATING
    validation = validator.validate(file_task.file_path, content)

    if not validation.is_valid:
        file_task.status = FileStatus.REPAIRING
        file_task.repair_attempts += 1

        if file_task.repair_attempts <= MAX_REPAIR_ATTEMPTS:
            repaired = await repair_agent.repair(
                file_task.file_path, content, validation, state
            )
            if repaired:
                content = repaired
                validation = validator.validate(file_task.file_path, content)

        if not validation.is_valid:
            file_task.status = FileStatus.FAILED
            file_task.error = validation.error_message
            if artifact_mgr:
                artifact_mgr.save_generation_log(
                    file_task.file_path, "validate", False, validation.error_message
                )
            state["validation_errors"] = state.get("validation_errors", {})
            state["validation_errors"][file_task.file_path] = (
                validation.error_message or "Unknown error"
            )
            state["status"] = "failed"
            state["error"] = f"Syntax error in {file_task.file_path}: {validation.error_message}"
            state["run_status"] = derive_run_status(state)
            return state

    # File is valid
    file_task.status = FileStatus.DONE
    file_task.content = content

    # Persist to disk
    if artifact_mgr:
        artifact_mgr.save_file(file_task.file_path, content)
        artifact_mgr.save_file_status(file_task)
        artifact_mgr.save_generation_log(file_task.file_path, "generate", True)

    # Track in state
    state["generated_files"] = state.get("generated_files", []) + [file_task.file_path]
    state["current_file_index"] = state.get("current_file_index", 0) + 1

    logger.info(
        "Generated file %s (%d/%d)",
        file_task.file_path,
        state["current_file_index"],
        len(project_plan.files),
    )

    return state


def _should_continue_file_generation(state: AgentState) -> Literal["generate_file", "tester"]:
    """Decide whether to generate more files or proceed to testing."""
    project_plan = state.get("project_plan")
    if not project_plan or not isinstance(project_plan, ProjectPlan):
        return "tester"

    if project_plan.all_done():
        return "tester"

    if project_plan.has_failures():
        return "tester"

    ready = project_plan.get_ready_tasks()
    if ready:
        return "generate_file"

    return "tester"


async def _tester_node(state: AgentState) -> AgentState:
    """Run the Tester agent with tracing."""
    agent = TesterAgent()
    run_id = state.get("run_id", "")
    with AgentTracer("tester", run_id) as tracer:
        result = await agent.run(state)
        tracer.record_tokens(
            result.get("tokens_used", 0),
            result.get("provider_used", ""),
            result.get("model_used", ""),
        )
        result["run_status"] = derive_run_status(result)
        return result


async def _reviewer_node(state: AgentState) -> AgentState:
    """Run the Reviewer agent with tracing."""
    agent = ReviewerAgent()
    run_id = state.get("run_id", "")
    with AgentTracer("reviewer", run_id) as tracer:
        result = await agent.run(state)
        tracer.record_tokens(
            result.get("tokens_used", 0),
            result.get("provider_used", ""),
            result.get("model_used", ""),
        )
        result["run_status"] = derive_run_status(result)
        return result


async def _documentation_node(state: AgentState) -> AgentState:
    """Run the Documentation agent with tracing."""
    agent = DocumentationAgent()
    run_id = state.get("run_id", "")
    with AgentTracer("documentation", run_id) as tracer:
        result = await agent.run(state)
        tracer.record_tokens(
            result.get("tokens_used", 0),
            result.get("provider_used", ""),
            result.get("model_used", ""),
        )
        result["run_status"] = derive_run_status(result)
        return result


def _should_retry_coder(state: AgentState) -> Literal["generate_file", "reviewer"]:
    """Decide whether to retry coder or proceed to reviewer.

    Returns 'generate_file' if tests failed AND iteration_count < MAX_ITERATIONS.
    Otherwise returns 'reviewer'.
    """
    test_results = state.get("test_results")
    iteration = state.get("iteration_count", 0)

    if test_results and test_results.failed > 0 and iteration < MAX_ITERATIONS:
        logger.info(
            "Tests failed (%d failed, iteration %d/%d), retrying coder",
            test_results.failed,
            iteration,
            MAX_ITERATIONS,
        )
        return "generate_file"

    return "reviewer"


def _should_continue(state: AgentState) -> Literal["documentation", "__end__"]:
    """Decide whether to continue to documentation or end (HITL/waiting).

    If status is 'waiting_approval' (critical finding), stop.
    Otherwise proceed to documentation.
    """
    status = state.get("status", "")
    if status == "waiting_approval":
        return "__end__"

    return "documentation"


def build_graph() -> StateGraph:
    """Build and return the complete agent orchestration graph.

    Flow:
        START → architect → planner → generate_file* → tester
        → (retry | reviewer) → documentation → END

    Conditional edges:
        - generate_file→generate_file if more files to generate
        - generate_file→tester if all files done
        - tester→generate_file if tests fail AND iteration_count < MAX_ITERATIONS
        - reviewer→documentation normally, reviewer→END if HITL triggered
    """
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("architect", _architect_node)
    graph.add_node("planner", _planner_node)
    graph.add_node("generate_file", _generate_file_node)
    graph.add_node("tester", _tester_node)
    graph.add_node("reviewer", _reviewer_node)
    graph.add_node("documentation", _documentation_node)

    # Entry point
    graph.set_entry_point("architect")

    # Edges
    graph.add_edge("architect", "planner")
    graph.add_edge("planner", "generate_file")

    # Conditional: generate_file → generate_file (next file) OR tester
    graph.add_conditional_edges(
        "generate_file",
        _should_continue_file_generation,
        {
            "generate_file": "generate_file",
            "tester": "tester",
        },
    )

    # Conditional: tester → generate_file (retry) OR reviewer
    graph.add_conditional_edges(
        "tester",
        _should_retry_coder,
        {
            "generate_file": "generate_file",
            "reviewer": "reviewer",
        },
    )

    # Conditional: reviewer → documentation OR end (HITL)
    graph.add_conditional_edges(
        "reviewer",
        _should_continue,
        {
            "documentation": "documentation",
            "__end__": END,
        },
    )

    graph.add_edge("documentation", END)

    return graph


def compile_graph(checkpointer=None):
    """Compile the StateGraph into a runnable graph.

    Args:
        checkpointer: Optional LangGraph checkpointer for persistence.

    Returns:
        Compiled graph ready to invoke.
    """
    graph = build_graph()
    return graph.compile(checkpointer=checkpointer)
