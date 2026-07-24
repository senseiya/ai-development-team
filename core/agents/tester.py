"""Tester Agent - generates and validates test code."""

from __future__ import annotations

import logging
import re

from core.agents.base import BaseAgent
from core.orchestrator.state import AgentState, TestResult, TestSuiteReport
from core.schemas import ModelCapability

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


class TesterAgent(BaseAgent):
    """Agent responsible for testing generated code.

    In Phase 4, this agent analyzes code via LLM.
    In Phase 5, it will execute tests in a sandbox.
    """

    name = "tester"
    capability = ModelCapability.CODE_GENERATION
    tools: list[str] = []

    async def run(self, state: AgentState) -> AgentState:
        """Execute the tester agent.

        Reads 'generated_code' from state, produces TestSuiteReport.

        Args:
            state: Must contain 'generated_code'.

        Returns:
            Updated AgentState with 'test_results' populated.
        """
        generated_code = state.get("generated_code", "")
        user_request = state.get("user_request", "")

        if not generated_code:
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

        prompt = (
            f"Original request:\n{user_request}\n\n"
            f"Generated code to test:\n```python\n{generated_code}\n```\n\n"
            f"Analyze this code and provide test results."
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
                import json

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
