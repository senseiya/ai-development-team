"""Task Scheduler - decomposes project into file-level tasks with dependencies."""

from __future__ import annotations

import json
import logging

from core.agents.base import BaseAgent
from core.orchestrator.state import AgentState, FileTask, ProjectPlan
from core.schemas import ModelCapability

logger = logging.getLogger(__name__)

SCHEDULER_SYSTEM_PROMPT = """You are a project architect. Your task is to decompose a software
project into individual files that need to be created, with their dependencies.

For each file, provide:
- file_path: relative path from project root
- description: what this file should contain and do
- dependencies: list of file_paths that must exist before this file

Guidelines:
- Start with config files (package.json, pyproject.toml, etc.)
- Then shared utilities/types
- Then core business logic
- Then API/routes layer
- Then tests
- Then documentation
- Each file should be self-contained but reference others via imports
- Keep descriptions specific enough for a developer to implement

Respond ONLY with a JSON object:
{
  "project_name": "name",
  "project_description": "brief description",
  "files": [
    {
      "file_path": "src/models/user.py",
      "description": "User model with fields: id, name, email, created_at",
      "dependencies": []
    }
  ]
}
"""


class TaskScheduler(BaseAgent):
    """Decomposes project into file-level tasks with dependency ordering."""

    name = "task_scheduler"
    capability = ModelCapability.REASONING
    tools: list[str] = []

    async def run(self, state: AgentState) -> AgentState:
        """Execute task scheduler.

        Reads user_request, produces ProjectPlan with file-level tasks.

        Args:
            state: Must contain 'user_request'.

        Returns:
            Updated AgentState with 'file_tasks' and 'project_plan' populated.
        """
        user_request = state.get("user_request", "")

        if not user_request:
            state["status"] = "failed"
            state["error"] = "No user request provided"
            self._add_message(state, "No user request provided", "error")
            return state

        prompt = (
            f"Decompose this project into individual files:\n\n{user_request}\n\n"
            "List every file that needs to be created, with dependencies."
        )

        try:
            response = await self.call_llm(
                prompt=prompt,
                system_prompt=SCHEDULER_SYSTEM_PROMPT,
                state=state,
            )

            plan = self._parse_plan(response.content)
            self._update_tokens(state, response.tokens_used)

            state["file_tasks"] = plan.files
            state["project_plan"] = plan
            state["status"] = "planning"
            self._add_message(
                state,
                f"Project decomposed into {len(plan.files)} files",
            )
            return state

        except Exception as e:
            logger.error("TaskScheduler failed: %s", str(e))
            state["status"] = "failed"
            state["error"] = str(e)
            self._add_message(state, f"Task scheduler failed: {e}", "error")
            return state

    def _parse_plan(self, content: str) -> ProjectPlan:
        """Parse LLM response into ProjectPlan."""
        text = content.strip()

        # Strip markdown code blocks
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [line for line in lines if not line.strip().startswith("```")]
            text = "\n".join(lines).strip()

        data = json.loads(text)

        plan = ProjectPlan(
            project_name=data.get("project_name", "project"),
            project_description=data.get("project_description", ""),
        )

        for item in data.get("files", []):
            plan.files.append(
                FileTask(
                    file_path=item.get("file_path", ""),
                    description=item.get("description", ""),
                    dependencies=item.get("dependencies", []),
                )
            )

        return plan
