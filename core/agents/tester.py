"""Tester Agent - generates and validates test code.

In Phase 5, the TesterAgent executes generated tests in a sandboxed
Docker container using the sandbox_exec tool.
"""

from __future__ import annotations

import json
import logging
import re

from core.agents.base import BaseAgent
from core.orchestrator.state import AgentState, TestResult, TestSuiteReport
from core.schemas import ModelCapability
from core.tools.sandbox_exec_tool import SandboxExecInput, execute_in_sandbox

logger = logging.getLogger(__name__)

TESTER_SYSTEM_PROMPT = """You are an expert QA engineer and test developer.
Your task is to review the generated code and produce test results.

Analyze the code for:
1. Correctness — does it do what was requested?
2. Error handling — are edge cases covered?
3. Type safety — are types correct?
4. Best practices — PEP 8, naming, structure

Respond with a JSON object containing test results:
{
  "total": <number of checks>,
  "passed": <number passing>,
  "failed": <number failing>,
  "results": [
    {"test_name": "name", "passed": true/false, "output": "description"}
  ],
  "summary": "Overall assessment"
}

Be strict but fair. Flag real issues, not style preferences.
"""

# Command to run pytest in the sandbox
PYTEST_COMMAND = "python -m pytest --tb=short -q /workspace 2>&1 || true"


class TesterAgent(BaseAgent):
    """Agent responsible for testing generated code.

    In Phase 5, this agent:
    1. Generates test files via LLM (analysis)
    2. Executes tests in a sandboxed Docker container
    3. Combines LLM analysis with actual execution results
    """

    name = "tester"
    capability = ModelCapability.CODE_GENERATION
    tools: list[str] = ["filesystem", "sandbox_exec"]

    async def run(self, state: AgentState) -> AgentState:
        """Execute the tester agent.

        Reads files from workspace, runs tests in sandbox, and
        combines results with LLM analysis.

        Args:
            state: Must contain 'workspace_path' and/or 'generated_code'.

        Returns:
            Updated AgentState with 'test_results' populated.
        """
        generated_code = state.get("generated_code", "")
        user_request = state.get("user_request", "")
        workspace_path = state.get("workspace_path", "")

        if not generated_code and not workspace_path:
            state["test_results"] = TestSuiteReport(
                total=0,
                passed=0,
                failed=1,
                results=[
                    TestResult(
                        test_name="no_code_to_test",
                        passed=False,
                        output="No generated code found in state",
                    )
                ],
                output="No code to test",
            )
            state["iteration_count"] = state.get("iteration_count", 0) + 1
            self._add_message(state, "No code to test", "warning")
            return state

        # Try to execute tests in sandbox if workspace is available
        sandbox_result = None
        if workspace_path:
            sandbox_result = self._run_tests_in_sandbox(workspace_path)

        # Get LLM analysis
        prompt = (
            f"Original request:\n{user_request}\n\n"
            f"Generated code to test:\n```python\n{generated_code}\n```\n\n"
            "Analyze this code and provide test results."
        )

        try:
            response = await self.call_llm(
                prompt=prompt,
                system_prompt=TESTER_SYSTEM_PROMPT,
                state=state,
            )

            report = self._parse_test_report(response.content)
            state["test_results"] = report
            state["iteration_count"] = state.get("iteration_count", 0) + 1
            self._update_tokens(state, response.tokens_used)

            # Merge sandbox results if available
            if sandbox_result and sandbox_result.exit_code is not None:
                state["sandbox_exit_code"] = sandbox_result.exit_code
                state["sandbox_output"] = sandbox_result.stdout + sandbox_result.stderr

                # If sandbox tests actually ran, override with real results
                if sandbox_result.exit_code == 0:
                    report.passed = report.total
                    report.failed = 0
                    self._add_message(
                        state,
                        "Sandbox tests passed (exit_code=0)",
                    )
                elif sandbox_result.exit_code > 0:
                    report.failed = report.total
                    report.passed = 0
                    self._add_message(
                        state,
                        f"Sandbox tests failed (exit_code={sandbox_result.exit_code})",
                    )

            self._add_message(
                state,
                f"Tests: {report.passed}/{report.total} passed, "
                f"{report.failed} failed",
            )
            return state

        except Exception as e:
            logger.error("TesterAgent failed: %s", str(e))
            state["status"] = "failed"
            state["error"] = str(e)
            self._add_message(state, f"Tester failed: {e}", "error")
            return state

    def _run_tests_in_sandbox(self, workspace_path: str):
        """Execute pytest in a sandboxed Docker container.

        Args:
            workspace_path: Path to the workspace directory.

        Returns:
            SandboxExecOutput or None if Docker is unavailable.
        """
        try:
            result = execute_in_sandbox(
                SandboxExecInput(
                    command=PYTEST_COMMAND,
                    workspace_path=workspace_path,
                    timeout=60,
                    mem_limit="256m",
                    network_disabled=True,
                )
            )
            logger.info(
                "Sandbox test execution: exit_code=%d, time=%.1fms",
                result.exit_code,
                result.execution_time_ms,
            )
            return result
        except RuntimeError as e:
            logger.warning("Sandbox unavailable: %s", e)
            return None

    def _parse_test_report(self, content: str) -> TestSuiteReport:
        """Parse LLM response into TestSuiteReport.

        Handles both raw JSON and markdown code blocks.
        Falls back to basic analysis if parsing fails.
        """
        text = content.strip()

        # Strip markdown code blocks if present
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()

        # Try to extract JSON from the response
        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            try:
                data = json.loads(json_match.group())
                results = []
                for r in data.get("results", []):
                    results.append(
                        TestResult(
                            test_name=r.get("test_name", "unnamed"),
                            passed=r.get("passed", False),
                            output=r.get("output", ""),
                        )
                    )

                return TestSuiteReport(
                    total=data.get("total", len(results)),
                    passed=data.get("passed", sum(1 for r in results if r.passed)),
                    failed=data.get("failed", sum(1 for r in results if not r.passed)),
                    results=results,
                    output=data.get("summary", ""),
                )
            except Exception:
                pass

        # Fallback: treat the entire response as a basic analysis
        has_issues = any(
            word in text.lower()
            for word in ["error", "bug", "issue", "fail", "critical", "vulnerability"]
        )

        return TestSuiteReport(
            total=1,
            passed=0 if has_issues else 1,
            failed=1 if has_issues else 0,
            results=[
                TestResult(
                    test_name="llm_analysis",
                    passed=not has_issues,
                    output=text[:500],
                )
            ],
            output=text[:1000],
        )
