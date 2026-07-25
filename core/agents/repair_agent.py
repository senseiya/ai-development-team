"""Repair Agent - fixes broken code using error context."""

from __future__ import annotations

import logging

from core.agents.base import BaseAgent
from core.agents.syntax_validator import ValidationResult
from core.orchestrator.state import AgentState
from core.schemas import ModelCapability

logger = logging.getLogger(__name__)

MAX_REPAIR_ATTEMPTS = 3

REPAIR_SYSTEM_PROMPT = """You are an expert code repair agent. Your task is to fix syntax errors
in generated code. You will receive:
1. The original broken code
2. The syntax error details (message, line number, column)

Fix ONLY the syntax error. Do not change the logic or structure.
Return the complete fixed file content.

Guidelines:
- Fix the specific syntax error mentioned
- Preserve the original code structure and logic
- Ensure the fix doesn't introduce new syntax errors
- Return ONLY the fixed code, no explanations"""


class RepairAgent(BaseAgent):
    """Fixes broken code using error context from syntax validation."""

    name = "repair_agent"
    capability = ModelCapability.CODE_GENERATION
    tools: list[str] = []

    async def repair(
        self,
        file_path: str,
        broken_content: str,
        validation_result: ValidationResult,
        state: AgentState,
    ) -> str | None:
        """Attempt to repair broken code.

        Args:
            file_path: Path to the broken file.
            broken_content: The broken code content.
            validation_result: The validation error details.
            state: Current AgentState.

        Returns:
            Fixed content if repair succeeded, None otherwise.
        """
        if validation_result.is_valid:
            return broken_content

        error_details = self._format_error(validation_result)

        prompt = (
            f"Fix the syntax error in this file:\n\n"
            f"File: {file_path}\n"
            f"{error_details}\n\n"
            f"Original code:\n```python\n{broken_content}\n```\n\n"
            "Return the complete fixed file content."
        )

        try:
            response = await self.call_llm(
                prompt=prompt,
                system_prompt=REPAIR_SYSTEM_PROMPT,
                state=state,
            )

            fixed_content = self._clean_response(response.content)
            self._update_tokens(state, response.tokens_used)

            logger.info("Repaired %s (attempt %s)", file_path, state.get("repair_attempts", 0))
            return fixed_content

        except Exception as e:
            logger.error("Repair failed for %s: %s", file_path, str(e))
            return None

    def _format_error(self, result: ValidationResult) -> str:
        """Format validation error for the repair prompt."""
        parts = [f"Error: {result.error_message}"]

        if result.line_number is not None:
            parts.append(f"Line: {result.line_number}")

        if result.column is not None:
            parts.append(f"Column: {result.column}")

        return "\n".join(parts)

    def _clean_response(self, content: str) -> str:
        """Clean LLM response to extract just the code."""
        text = content.strip()

        # Strip markdown code blocks
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first line (```language)
            if lines:
                lines = lines[1:]
            # Remove last line (```)
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        return text.strip()

    async def run(self, state: AgentState) -> AgentState:
        """Execute repair agent (called from graph).

        This is the standard agent interface. For actual repair,
        use the repair() method directly.
        """
        # This method is called from the graph but repair is done
        # via the repair() method in the pipeline
        return state
