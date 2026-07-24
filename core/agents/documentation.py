"""Documentation Agent - generates documentation for completed code."""

from __future__ import annotations

import logging

from core.agents.base import BaseAgent
from core.orchestrator.state import AgentState
from core.schemas import ModelCapability

logger = logging.getLogger(__name__)

DOCUMENTATION_SYSTEM_PROMPT = """You are a technical writer creating documentation for
newly generated code. Write clear, concise documentation.

Produce the following sections:
1. **Overview** — What the code does (1-2 sentences)
2. **Installation** — How to install dependencies (if applicable)
3. **Usage** — Code examples showing how to use the main functions/classes
4. **API Reference** — Brief description of each public function/class
5. **Notes** — Any caveats, limitations, or important design decisions

Guidelines:
- Write for developers who haven't seen the code
- Include type information in examples
- Keep it concise — no fluff
- Use markdown formatting
"""


class DocumentationAgent(BaseAgent):
    """Agent responsible for generating project documentation."""

    name = "documentation"
    capability = ModelCapability.SUMMARIZATION
    tools: list[str] = []

    async def run(self, state: AgentState) -> AgentState:
        """Execute the documentation agent.

        Reads 'generated_code' and 'user_request', produces documentation.

        Args:
            state: Must contain 'generated_code' and 'user_request'.

        Returns:
            Updated AgentState with 'documentation' populated.
        """
        generated_code = state.get("generated_code", "")
        user_request = state.get("user_request", "")
        review_findings = state.get("review_findings", [])

        if not generated_code:
            state["documentation"] = "No code available to document."
            self._add_message(state, "No code to document", "warning")
            return state

        # Build context for the documentation agent
        findings_summary = ""
        if review_findings:
            findings_list = []
            for f in review_findings:
                findings_list.append(
                    f"- [{f.severity.value}] {f.category}: {f.description}"
                )
            findings_summary = (
                "\n\nReview findings to address in documentation:\n"
                + "\n".join(findings_list)
            )

        prompt = (
            f"Original request:\n{user_request}\n\n"
            f"Generated code:\n```python\n{generated_code}\n```"
            f"{findings_summary}\n\n"
            f"Generate documentation for this code."
        )

        try:
            response = await self.call_llm(
                prompt=prompt,
                system_prompt=DOCUMENTATION_SYSTEM_PROMPT,
                state=state,
            )

            state["documentation"] = response.content
            state["status"] = "documenting"
            self._update_tokens(state, response.tokens_used)
            self._add_message(
                state,
                f"Documentation generated ({len(response.content)} chars)",
            )
            return state

        except Exception as e:
            logger.error("DocumentationAgent failed: %s", str(e))
            state["status"] = "failed"
            state["error"] = str(e)
            self._add_message(state, f"Documentation failed: {e}", "error")
            return state
