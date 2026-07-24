"""LangGraph StateGraph for the multi-agent orchestration.

Defines the complete agent pipeline:
  planner → coder → tester → reviewer → documentation → done

With conditional edges:
  - tester → coder (if tests fail AND iteration_count < MAX_ITERATIONS)
  - reviewer → END (if severity=critical → waiting_approval)
  - any node → failed (on unhandled exception)

Phase 7: Each node is instrumented with AgentTracer for Prometheus metrics.
"""

from __future__ import annotations

import logging
from typing import Literal

from langgraph.graph import END, StateGraph

from core.agents.coder import CoderAgent
from core.agents.documentation import DocumentationAgent
from core.agents.planner import PlannerAgent
from core.agents.reviewer import ReviewerAgent
from core.agents.tester import TesterAgent
from core.observability.tracing import AgentTracer
from core.orchestrator.state import AgentState

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 3


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
        return result


async def _coder_node(state: AgentState) -> AgentState:
    """Run the Coder agent with tracing."""
    agent = CoderAgent()
    run_id = state.get("run_id", "")
    with AgentTracer("coder", run_id) as tracer:
        result = await agent.run(state)
        tracer.record_tokens(
            result.get("tokens_used", 0),
            result.get("provider_used", ""),
            result.get("model_used", ""),
        )
        return result


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
        return result


def _should_retry_coder(state: AgentState) -> Literal["coder", "reviewer"]:
    """Decide whether to retry coder or proceed to reviewer.

    Returns 'coder' if tests failed AND iteration_count < MAX_ITERATIONS.
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
        return "coder"

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
        START → planner → coder → tester → (retry coder | reviewer) → documentation → END

    Conditional edges:
        - tester→coder if tests fail AND iteration_count < MAX_ITERATIONS
        - reviewer→documentation normally, reviewer→END if HITL triggered
    """
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("planner", _planner_node)
    graph.add_node("coder", _coder_node)
    graph.add_node("tester", _tester_node)
    graph.add_node("reviewer", _reviewer_node)
    graph.add_node("documentation", _documentation_node)

    # Entry point
    graph.set_entry_point("planner")

    # Edges
    graph.add_edge("planner", "coder")
    graph.add_edge("coder", "tester")

    # Conditional: tester → coder (retry) OR reviewer
    graph.add_conditional_edges(
        "tester",
        _should_retry_coder,
        {
            "coder": "coder",
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
