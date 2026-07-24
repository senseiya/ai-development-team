"""Coder Agent - generates code based on user requests."""

from __future__ import annotations

import logging
from typing import Any

from core.agents.base import BaseAgent
from core.schemas import ModelCapability

logger = logging.getLogger(__name__)

CODER_SYSTEM_PROMPT = """You are an expert software developer. Your task is to generate
high-quality, clean, and well-documented code based on the user's request.

Guidelines:
- Write production-ready code
- Include proper error handling
- Follow Python best practices (PEP 8, type hints)
- Add docstrings to functions and classes
- If the request is ambiguous, make reasonable assumptions and document them
- Return only the code, no explanations outside code blocks
"""


class CoderAgent(BaseAgent):
    """Agent responsible for generating code from user requests."""

    name = "coder"
    capability = ModelCapability.CODE_GENERATION
    tools: list[str] = []

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Execute the coder agent.

        Args:
            state: Must contain 'user_request' with the task description.
                May contain 'router' (ModelRouter) for automatic model selection.

        Returns:
            Updated state with 'generated_code', 'model_used', 'provider_used',
            and 'status'.
        """
        user_request = state.get("user_request", "")
        router = state.get("router")

        if not user_request:
            return {
                **state,
                "status": "failed",
                "error": "No user request provided",
            }

        prompt = f"Generate code for the following request:\n\n{user_request}"

        try:
            response = await self.call_llm(
                prompt=prompt,
                system_prompt=CODER_SYSTEM_PROMPT,
                router=router,
            )

            return {
                **state,
                "generated_code": response.content,
                "tokens_used": state.get("tokens_used", 0) + response.tokens_used,
                "model_used": response.model,
                "provider_used": response.provider,
                "status": "completed",
            }

        except Exception as e:
            logger.error("CoderAgent failed: %s", str(e))
            return {
                **state,
                "status": "failed",
                "error": str(e),
            }
