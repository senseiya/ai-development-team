"""Coder Agent - generates code based on user requests."""

from __future__ import annotations

import logging

from core.agents.base import BaseAgent
from core.orchestrator.state import AgentState
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

    async def run(self, state: AgentState) -> AgentState:
        """Execute the coder agent.

        Args:
            state: Must contain 'user_request' with the task description.

        Returns:
            Updated AgentState with 'generated_code', 'model_used',
            'provider_used', and 'status'.
        """
        user_request = state.get("user_request", "")

        if not user_request:
            state["status"] = "failed"
            state["error"] = "No user request provided"
            self._add_message(state, "No user request provided", "error")
            return state

        prompt = f"Generate code for the following request:\n\n{user_request}"

        try:
            response = await self.call_llm(
                prompt=prompt,
                system_prompt=CODER_SYSTEM_PROMPT,
                state=state,
            )

            state["generated_code"] = response.content
            self._update_tokens(state, response.tokens_used)
            state["model_used"] = response.model
            state["provider_used"] = response.provider
            state["status"] = "completed"
            self._add_message(
                state,
                f"Code generated using {response.model} ({response.provider})",
            )
            return state

        except Exception as e:
            logger.error("CoderAgent failed: %s", str(e))
            state["status"] = "failed"
            state["error"] = str(e)
            self._add_message(state, f"Coder failed: {e}", "error")
            return state
