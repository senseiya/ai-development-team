"""Planner Agent - decomposes user requests into actionable subtasks."""

from __future__ import annotations

import json
import logging
import uuid

from core.agents.base import BaseAgent
from core.orchestrator.state import AgentState, SubTask
from core.schemas import ModelCapability

logger = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = """You are a senior software architect and project planner.
Your task is to decompose a user's request into a clear, ordered plan of subtasks.

Each subtask must have:
- A unique ID (use short strings like "1", "2", "3")
- A concise title
- A detailed description of what needs to be done
- A list of dependency IDs (subtasks that must complete before this one)
- Status: "pending"

Guidelines:
- Break complex tasks into small, testable units
- Identify dependencies between subtasks
- Order subtasks so independent ones can run in parallel
- Keep the plan realistic — don't over-decompose trivial requests
- For simple requests, 1-3 subtasks are enough

Respond ONLY with a JSON array of subtasks. Example:
[
  {"id": "1", "title": "Setup project",
   "description": "Initialize project structure", "dependencies": []},
  {"id": "2", "title": "Implement API",
   "description": "Create REST endpoints", "dependencies": ["1"]}
]
"""


class PlannerAgent(BaseAgent):
    """Agent responsible for decomposing requests into subtask plans."""

    name = "planner"
    capability = ModelCapability.REASONING
    tools: list[str] = []

    async def run(self, state: AgentState) -> AgentState:
        """Execute the planner agent.

        Reads user_request, produces a list of SubTasks in state["plan"].

        Args:
            state: Must contain 'user_request'.

        Returns:
            Updated AgentState with 'plan' populated.
        """
        user_request = state.get("user_request", "")

        if not user_request:
            state["status"] = "failed"
            state["error"] = "No user request provided"
            self._add_message(state, "No user request provided", "error")
            return state

        prompt = f"Decompose the following request into a plan of subtasks:\n\n{user_request}"

        try:
            response = await self.call_llm(
                prompt=prompt,
                system_prompt=PLANNER_SYSTEM_PROMPT,
                state=state,
            )

            # Parse the JSON array of subtasks
            subtasks = self._parse_subtasks(response.content)

            state["plan"] = subtasks
            state["status"] = "planning"
            self._update_tokens(state, response.tokens_used)
            self._add_message(
                state,
                f"Plan created with {len(subtasks)} subtasks",
            )
            return state

        except json.JSONDecodeError as e:
            logger.error("PlannerAgent: failed to parse LLM response as JSON: %s", e)
            # Create a single subtask with the full request
            state["plan"] = [
                SubTask(
                    id=str(uuid.uuid4())[:8],
                    title="Execute request",
                    description=user_request,
                    dependencies=[],
                )
            ]
            state["status"] = "planning"
            self._add_message(
                state,
                "LLM response not parseable, created single fallback subtask",
                "warning",
            )
            return state

        except Exception as e:
            logger.error("PlannerAgent failed: %s", str(e))
            state["status"] = "failed"
            state["error"] = str(e)
            self._add_message(state, f"Planner failed: {e}", "error")
            return state

    def _parse_subtasks(self, content: str) -> list[SubTask]:
        """Parse LLM response into SubTask list.

        Handles both raw JSON and markdown code blocks containing JSON.
        """
        text = content.strip()

        # Strip markdown code blocks if present
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first and last lines (``` markers)
            lines = [line for line in lines if not line.strip().startswith("```")]
            text = "\n".join(lines).strip()

        data = json.loads(text)

        if not isinstance(data, list):
            data = [data]

        subtasks = []
        for item in data:
            subtasks.append(
                SubTask(
                    id=item.get("id", str(uuid.uuid4())[:8]),
                    title=item.get("title", "Untitled"),
                    description=item.get("description", ""),
                    dependencies=item.get("dependencies", []),
                )
            )

        return subtasks
