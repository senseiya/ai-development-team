"""Reviewer Agent - performs code review with severity-based findings."""

from __future__ import annotations

import json
import logging
import re
import uuid

from core.agents.base import BaseAgent
from core.orchestrator.state import (
    AgentState,
    ReviewFinding,
    Severity,
)
from core.schemas import ModelCapability

logger = logging.getLogger(__name__)

REVIEWER_SYSTEM_PROMPT = """You are a senior code reviewer specializing in security,
performance, and code quality. Review the generated code thoroughly.

For each finding, assign a severity:
- "critical": Security vulnerabilities, data loss risks, production-breaking bugs
  -> These STOP the pipeline and require human approval
- "warning": Performance issues, potential bugs, anti-patterns
  -> These are logged but don't stop the pipeline
- "info": Style suggestions, minor improvements
  -> Informational only

Respond with a JSON object:
{
  "findings": [
    {
      "id": "unique-id",
      "severity": "critical|warning|info",
      "category": "security|performance|style|bug|logic",
      "file_path": "filename.py (if applicable)",
      "line_number": 42,
      "description": "What's wrong",
      "suggestion": "How to fix it"
    }
  ],
  "summary": "Overall review assessment",
  "approved": true/false
}

Be thorough on security checks: SQL injection, XSS, path traversal,
hardcoded secrets, unsafe deserialization, etc.
"""


class ReviewerAgent(BaseAgent):
    """Agent responsible for code review with severity-based findings.

    Critical findings trigger HITL (human-in-the-loop) approval.
    """

    name = "reviewer"
    capability = ModelCapability.CODE_REVIEW
    tools: list[str] = []

    async def run(self, state: AgentState) -> AgentState:
        """Execute the reviewer agent.

        Reads 'generated_code' from state, produces ReviewFindings.

        Args:
            state: Must contain 'generated_code'.

        Returns:
            Updated AgentState with 'review_findings' populated.
            If any finding has severity=critical, status becomes
            'waiting_approval'.
        """
        generated_code = state.get("generated_code", "")
        user_request = state.get("user_request", "")

        if not generated_code:
            state["review_findings"] = [
                ReviewFinding(
                    id=str(uuid.uuid4())[:8],
                    severity=Severity.WARNING,
                    category="logic",
                    description="No generated code to review",
                )
            ]
            self._add_message(state, "No code to review", "warning")
            return state

        prompt = (
            f"Original request:\n{user_request}\n\n"
            f"Code to review:\n```python\n{generated_code}\n```\n\n"
            f"Perform a thorough code review."
        )

        try:
            response = await self.call_llm(
                prompt=prompt,
                system_prompt=REVIEWER_SYSTEM_PROMPT,
                state=state,
            )

            findings = self._parse_findings(response.content)
            state["review_findings"] = findings
            self._update_tokens(state, response.tokens_used)

            # Check for critical findings → HITL
            critical = [f for f in findings if f.severity == Severity.CRITICAL]
            if critical:
                state["status"] = "waiting_approval"
                self._add_message(
                    state,
                    f"HITL triggered: {len(critical)} critical finding(s)",
                    "warning",
                )
            else:
                self._add_message(
                    state,
                    f"Review complete: {len(findings)} finding(s) "
                    f"({sum(1 for f in findings if f.severity == Severity.CRITICAL)} critical, "
                    f"{sum(1 for f in findings if f.severity == Severity.WARNING)} warnings)",
                )

            return state

        except Exception as e:
            logger.error("ReviewerAgent failed: %s", str(e))
            state["status"] = "failed"
            state["error"] = str(e)
            self._add_message(state, f"Reviewer failed: {e}", "error")
            return state

    def _parse_findings(self, content: str) -> list[ReviewFinding]:
        """Parse LLM response into ReviewFinding list.

        Handles JSON with findings array, or falls back to
        treating the response as a single finding.
        """
        text = content.strip()

        # Strip markdown code blocks
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [line for line in lines if not line.strip().startswith("```")]
            text = "\n".join(lines).strip()

        # Try to extract JSON
        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            try:
                data = json.loads(json_match.group())
                findings = []
                for f in data.get("findings", []):
                    severity_str = f.get("severity", "info").lower()
                    try:
                        severity = Severity(severity_str)
                    except ValueError:
                        severity = Severity.INFO

                    findings.append(
                        ReviewFinding(
                            id=f.get("id", str(uuid.uuid4())[:8]),
                            severity=severity,
                            category=f.get("category", "style"),
                            file_path=f.get("file_path"),
                            line_number=f.get("line_number"),
                            description=f.get("description", ""),
                            suggestion=f.get("suggestion", ""),
                        )
                    )
                return findings
            except Exception:
                pass

        # Fallback: single finding from raw text
        has_critical = any(
            word in text.lower() for word in ["critical", "vulnerability", "security", "injection"]
        )
        has_warning = any(
            word in text.lower() for word in ["warning", "issue", "bug", "error", "problem"]
        )

        severity = (
            Severity.CRITICAL
            if has_critical
            else (Severity.WARNING if has_warning else Severity.INFO)
        )

        return [
            ReviewFinding(
                id=str(uuid.uuid4())[:8],
                severity=severity,
                category="security" if has_critical else "style",
                description=text[:500],
            )
        ]
