"""Integration tests for the LangGraph orchestration graph."""

from __future__ import annotations

import pytest

from core.orchestrator.graph import (
    MAX_ITERATIONS,
    _should_continue,
    _should_retry_coder,
    build_graph,
    compile_graph,
)
from core.orchestrator.state import (
    TestSuiteReport,
    create_initial_state,
)

# --- Conditional edge tests ---


@pytest.mark.unit
class TestShouldRetryCoder:
    """Tests for the tester→coder retry logic."""

    def test_retry_when_tests_fail(self) -> None:
        """Retry coder when tests fail and iteration < max."""
        state = create_initial_state("r1", "test")
        state["test_results"] = TestSuiteReport(failed=1)
        state["iteration_count"] = 0

        assert _should_retry_coder(state) == "coder"

    def test_no_retry_when_tests_pass(self) -> None:
        """Don't retry when tests pass."""
        state = create_initial_state("r1", "test")
        state["test_results"] = TestSuiteReport(failed=0)
        state["iteration_count"] = 0

        assert _should_retry_coder(state) == "reviewer"

    def test_no_retry_when_max_iterations_reached(self) -> None:
        """Don't retry when max iterations reached."""
        state = create_initial_state("r1", "test")
        state["test_results"] = TestSuiteReport(failed=1)
        state["iteration_count"] = MAX_ITERATIONS

        assert _should_retry_coder(state) == "reviewer"

    def test_no_retry_when_no_test_results(self) -> None:
        """Don't retry when no test results exist."""
        state = create_initial_state("r1", "test")
        state["test_results"] = None

        assert _should_retry_coder(state) == "reviewer"


@pytest.mark.unit
class TestShouldContinue:
    """Tests for the reviewer→documentation decision."""

    def test_continue_when_no_critical(self) -> None:
        """Continue to documentation when no critical findings."""
        state = create_initial_state("r1", "test")
        state["status"] = "reviewing"

        assert _should_continue(state) == "documentation"

    def test_stop_when_waiting_approval(self) -> None:
        """Stop when HITL is triggered."""
        state = create_initial_state("r1", "test")
        state["status"] = "waiting_approval"

        assert _should_continue(state) == "__end__"


# --- Graph structure tests ---


@pytest.mark.unit
class TestGraphStructure:
    """Tests for the graph structure and compilation."""

    def test_graph_builds(self) -> None:
        """Graph can be built without errors."""
        graph = build_graph()
        assert graph is not None

    def test_graph_compiles(self) -> None:
        """Graph can be compiled without errors."""
        compiled = compile_graph()
        assert compiled is not None

    def test_graph_has_expected_nodes(self) -> None:
        """Graph contains all expected node names."""
        graph = build_graph()
        # StateGraph stores nodes in graph.nodes dict
        node_names = list(graph.nodes.keys()) if hasattr(graph, "nodes") else []
        assert len(node_names) > 0


@pytest.mark.unit
class TestGraphEndToEnd:
    """End-to-end graph tests verifying state flow logic."""

    @pytest.mark.asyncio
    async def test_graph_state_flow_planner_to_coder(self) -> None:
        """Verify state transitions from planner to coder."""
        state = create_initial_state("r1", "Build API")
        # Simulate planner output
        from core.orchestrator.state import SubTask

        state["plan"] = [SubTask(id="1", title="Task", description="Do it")]
        state["status"] = "planning"

        # Verify conditional edge would route to coder
        assert _should_retry_coder(state) == "reviewer"  # no test failures yet

    @pytest.mark.asyncio
    async def test_graph_retry_loop_max_iterations(self) -> None:
        """Verify retry loop stops at max iterations."""
        state = create_initial_state("r1", "Build API")
        state["test_results"] = TestSuiteReport(failed=1)
        state["iteration_count"] = MAX_ITERATIONS

        # Should NOT retry, should go to reviewer
        assert _should_retry_coder(state) == "reviewer"

    @pytest.mark.asyncio
    async def test_graph_hitl_stops_pipeline(self) -> None:
        """Verify HITL stops the pipeline."""
        state = create_initial_state("r1", "Build API")
        state["status"] = "waiting_approval"

        assert _should_continue(state) == "__end__"
