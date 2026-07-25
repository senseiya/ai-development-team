"""Planner Agent - decomposes user requests into file-level tasks.

The Planner does NOT make architectural decisions. It reads the
ProjectBlueprint (produced by the Architect) and decomposes the
project into file-level tasks following that blueprint exactly.
"""

from __future__ import annotations

import json
import logging

from core.agents.base import BaseAgent
from core.agents.task_scheduler import TaskScheduler
from core.orchestrator.state import AgentState, ProjectBlueprint, SubTask
from core.schemas import ModelCapability

logger = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = """You are a software project planner. Your task is to decompose a
project into individual files that need to be created, following the
ProjectBlueprint exactly.

The Blueprint defines the architecture, frameworks, patterns, and structure.
You MUST follow it — do not make your own architectural decisions.

For each file, provide:
- file_path: relative path from project root
- description: what this file should contain and do
- dependencies: list of file_paths that must exist before this file

Guidelines:
- Start with config files (pyproject.toml, package.json, etc.)
- Then shared utilities/types
- Then models/schemas
- Then services/business logic
- Then routes/API layer
- Then tests
- Then documentation
- Use the directory_structure from the Blueprint
- Use the dependencies from the Blueprint for config files
- Each file should be self-contained but reference others via imports
- Keep descriptions specific enough for a developer to implement
- Do NOT choose frameworks, patterns, or tools — follow the Blueprint

Respond ONLY with a JSON object:
{
  "files": [
    {
      "file_path": "src/models/user.py",
      "description": "User model with fields: id, name, email, created_at",
      "dependencies": []
    }
  ]
}
"""


class PlannerAgent(BaseAgent):
    """Agent responsible for decomposing requests into file-level tasks.

    Reads the ProjectBlueprint and produces a ProjectPlan with file tasks.
    Does not make architectural decisions — follows the blueprint exactly.
    """

    name = "planner"
    capability = ModelCapability.REASONING
    tools: list[str] = []

    def __init__(self) -> None:
        self._scheduler = TaskScheduler()

    async def run(self, state: AgentState) -> AgentState:
        """Execute the planner agent.

        Reads ProjectBlueprint, uses TaskScheduler to decompose into files.

        Args:
            state: Must contain 'user_request' and 'project_blueprint'.

        Returns:
            Updated AgentState with 'file_tasks' and 'project_plan' populated.
        """
        blueprint = state.get("project_blueprint")
        if not blueprint or not isinstance(blueprint, ProjectBlueprint):
            state["status"] = "failed"
            state["error"] = "No ProjectBlueprint available. Run Architect first."
            self._add_message(state, "No ProjectBlueprint available", "error")
            return state

        # Inject blueprint context into user_request for TaskScheduler
        state = self._inject_blueprint_context(state, blueprint)

        # Use TaskScheduler to get file-level decomposition
        try:
            state = await self._scheduler.run(state)
            if state.get("status") == "failed":
                return state

            # Also create legacy SubTasks for backward compatibility
            plan = state.get("project_plan")
            if plan:
                subtasks = self._create_subtasks_from_plan(plan)
                state["plan"] = subtasks

            self._add_message(
                state,
                f"Plan created: {len(state.get('file_tasks', []))} files "
                f"following {blueprint.architecture} architecture",
            )
            return state

        except Exception as e:
            logger.error("PlannerAgent failed: %s", str(e))
            state["status"] = "failed"
            state["error"] = str(e)
            self._add_message(state, f"Planner failed: {e}", "error")
            return state

    def _inject_blueprint_context(
        self, state: AgentState, blueprint: ProjectBlueprint
    ) -> AgentState:
        """Inject blueprint context into state for TaskScheduler."""
        # Create a structured prompt for the TaskScheduler
        blueprint_json = json.dumps({
            "project_name": blueprint.project_name,
            "project_type": blueprint.project_type,
            "backend": blueprint.backend,
            "backend_language": blueprint.backend_language,
            "database": blueprint.database,
            "orm": blueprint.orm,
            "patterns": blueprint.patterns,
            "architecture": blueprint.architecture,
            "directory_structure": blueprint.directory_structure,
            "dependencies": blueprint.dependencies,
            "dev_dependencies": blueprint.dev_dependencies,
            "testing": blueprint.testing,
            "linting": blueprint.linting,
            "docker": blueprint.docker,
            "authentication": blueprint.authentication,
            "api_style": blueprint.api_style,
        }, indent=2)

        # Enhance user_request with blueprint context
        original_request = state.get("user_request", "")
        state["user_request"] = (
            f"{original_request}\n\n"
            f"=== Project Blueprint (FOLLOW EXACTLY) ===\n"
            f"{blueprint_json}\n"
            f"=== End Blueprint ==="
        )
        return state

    def _create_subtasks_from_plan(self, plan: object) -> list[SubTask]:
        """Create legacy SubTasks from ProjectPlan for backward compatibility."""
        from core.orchestrator.state import ProjectPlan

        if not isinstance(plan, ProjectPlan):
            return []

        subtasks = []
        for i, file_task in enumerate(plan.files):
            subtasks.append(
                SubTask(
                    id=str(i + 1),
                    title=file_task.file_path,
                    description=file_task.description,
                    dependencies=file_task.dependencies,
                )
            )
        return subtasks
