"""Architect Agent - designs project architecture before any code is generated.

The Architect is the first agent in the pipeline. It reads the user's request
and produces a ProjectBlueprint — a structured, deterministic architectural
decision document. It never generates code, files, or implementations.

Every downstream agent reads the Blueprint to stay consistent.
"""

from __future__ import annotations

import json
import logging

from core.agents.base import BaseAgent
from core.orchestrator.state import AgentState, BlueprintDecision, ProjectBlueprint
from core.schemas import ModelCapability

logger = logging.getLogger(__name__)

ARCHITECT_SYSTEM_PROMPT = """You are a senior Software Architect. Your ONLY job is to analyze
a user's project request and produce a complete ProjectBlueprint.

The Blueprint is a structured JSON object that defines EVERY architectural
decision for the project. All downstream agents will follow this blueprint
exactly — they will NOT make their own architectural choices.

Rules:
- You make ALL technical decisions: frameworks, patterns, structure, tooling
- Be specific and opinionated — no "it depends" or "use whatever"
- Choose technologies that work well together
- Prefer free, open-source tools
- Keep the stack simple and practical
- Every field MUST be filled — no empty strings
- For each decision, include a "decisions" entry explaining WHY you chose it
- Return ONLY valid JSON, no markdown, no explanations

Respond with a JSON object matching this EXACT structure:
{
  "project_name": "string",
  "project_type": "web_api|cli|library|fullstack|microservice",
  "description": "string",
  "backend": "FastAPI|Django|Express|Gin|Flask|none",
  "backend_language": "python|typescript|go|rust|javascript",
  "frontend": "React|Vue|HTMX|HTML+CSS|Svelte|none",
  "frontend_language": "typescript|javascript|none",
  "database": "PostgreSQL|SQLite|MongoDB|MySQL|none",
  "orm": "SQLAlchemy|Prisma|GORM|Django ORM|none",
  "cache": "Redis|none",
  "authentication": "JWT|OAuth2|API_KEY|session|none",
  "authorization": "RBAC|simple_role|none",
  "api_style": "REST|GraphQL|gRPC|none",
  "api_versioning": "url_path|header|none",
  "patterns": ["Repository", "Service Layer", "DTO", "Factory", "Strategy"],
  "architecture": "layered|hexagonal|clean|modular|monolith",
  "directory_structure": ["src/", "src/models/", "src/routes/", ...],
  "dependencies": ["fastapi", "sqlalchemy", "pydantic", ...],
  "dev_dependencies": ["pytest", "ruff", "mypy", ...],
  "testing": ["pytest", "httpx", "coverage"],
  "linting": ["ruff"],
  "formatter": ["ruff format"],
  "type_checker": ["mypy"],
  "docker": true|false,
  "ci_cd": "github_actions|gitlab_ci|none",
  "environment_variables": {"DATABASE_URL": "postgresql://...", "SECRET_KEY": "..."},
  "quality_rules": ["All functions must have type hints", ...],
  "documentation_strategy": "docstrings|external|inline|none",
  "coding_conventions": ["PEP 8", "max line length 100", ...],
  "security_requirements": ["Input validation", "SQL injection prevention", ...],
  "performance_requirements": ["Response time < 200ms", ...],
  "deployment_target": "local|docker|aws|gcp|railway|render",
  "decisions": [
    {
      "category": "database",
      "selected": "PostgreSQL",
      "rationale": "Excelente soporte para transacciones, JSONB y escalabilidad.",
      "alternatives": ["SQLite", "MySQL"]
    },
    {
      "category": "orm",
      "selected": "SQLAlchemy",
      "rationale": "ORM más maduro para Python, integración nativa con FastAPI.",
      "alternatives": ["Prisma"]
    }
  ]
}
"""

# Fallback blueprint for when LLM parsing fails
FALLBACK_BLUEPRINT = ProjectBlueprint(
    project_name="project",
    project_type="web_api",
    description="Generated project",
    backend="FastAPI",
    backend_language="python",
    frontend="HTML+CSS",
    frontend_language="none",
    database="PostgreSQL",
    orm="SQLAlchemy",
    cache="none",
    authentication="JWT",
    authorization="none",
    api_style="REST",
    api_versioning="url_path",
    patterns=["Repository", "Service Layer"],
    architecture="layered",
    directory_structure=[
        "src/",
        "src/models/",
        "src/routes/",
        "src/services/",
        "src/schemas/",
        "tests/",
    ],
    dependencies=["fastapi", "sqlalchemy", "pydantic", "uvicorn"],
    dev_dependencies=["pytest", "ruff", "mypy", "httpx"],
    testing=["pytest", "httpx"],
    linting=["ruff"],
    formatter=["ruff format"],
    type_checker=["mypy"],
    docker=False,
    ci_cd="github_actions",
    environment_variables={},
    quality_rules=[
        "All functions must have type hints",
        "All public functions must have docstrings",
    ],
    documentation_strategy="docstrings",
    coding_conventions=["PEP 8", "max line length 100"],
    security_requirements=["Input validation", "SQL injection prevention"],
    performance_requirements=[],
    deployment_target="docker",
)


class ArchitectAgent(BaseAgent):
    """Agent responsible for designing project architecture.

    Reads the user's request and produces a ProjectBlueprint that
    every downstream agent follows. Never generates code.
    """

    name = "architect"
    capability = ModelCapability.REASONING
    tools: list[str] = []

    async def run(self, state: AgentState) -> AgentState:
        """Execute the architect agent.

        Reads user_request, produces ProjectBlueprint in state.

        Args:
            state: Must contain 'user_request'.

        Returns:
            Updated AgentState with 'project_blueprint' and 'blueprint_summary'.
        """
        user_request = state.get("user_request", "")

        if not user_request:
            state["status"] = "failed"
            state["error"] = "No user request provided"
            self._add_message(state, "No user request provided", "error")
            return state

        prompt = (
            "Analyze this project request and produce a complete ProjectBlueprint.\n\n"
            f"User request:\n{user_request}\n\n"
            "Make ALL architectural decisions. Be specific and opinionated.\n"
            "For each major decision, include a 'decisions' entry with your rationale.\n"
            "Return ONLY the JSON Blueprint, nothing else."
        )

        try:
            response = await self.call_llm(
                prompt=prompt,
                system_prompt=ARCHITECT_SYSTEM_PROMPT,
                state=state,
                temperature=0.3,
            )

            blueprint = self._parse_blueprint(response.content)
            self._update_tokens(state, response.tokens_used)

            state["project_blueprint"] = blueprint
            state["blueprint_summary"] = blueprint.to_human_readable()
            state["status"] = "planning"

            self._add_message(
                state,
                f"Blueprint created: {blueprint.project_name} "
                f"({blueprint.backend}/{blueprint.database})",
            )
            return state

        except Exception as e:
            logger.error("ArchitectAgent failed: %s", str(e))
            state["status"] = "failed"
            state["error"] = str(e)
            self._add_message(state, f"Architect failed: {e}", "error")
            return state

    def _parse_blueprint(self, content: str) -> ProjectBlueprint:
        """Parse LLM response into ProjectBlueprint.

        Handles raw JSON and markdown code blocks.
        """
        text = content.strip()

        # Strip markdown code blocks
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [line for line in lines if not line.strip().startswith("```")]
            text = "\n".join(lines).strip()

        data = json.loads(text)

        # Parse decisions if present
        decisions_data = data.get("decisions", [])
        decisions = []
        for d in decisions_data:
            decisions.append(
                BlueprintDecision(
                    category=d.get("category", ""),
                    selected=d.get("selected", ""),
                    rationale=d.get("rationale", ""),
                    alternatives=d.get("alternatives", []),
                )
            )

        return ProjectBlueprint(
            blueprint_version=data.get("blueprint_version", 1),
            schema_version=data.get("schema_version", 1),
            project_name=data.get("project_name", ""),
            project_type=data.get("project_type", "web_api"),
            description=data.get("description", ""),
            backend=data.get("backend", ""),
            backend_language=data.get("backend_language", "python"),
            frontend=data.get("frontend", ""),
            frontend_language=data.get("frontend_language", "none"),
            database=data.get("database", ""),
            orm=data.get("orm", ""),
            cache=data.get("cache", "none"),
            authentication=data.get("authentication", ""),
            authorization=data.get("authorization", "none"),
            api_style=data.get("api_style", "REST"),
            api_versioning=data.get("api_versioning", "none"),
            patterns=data.get("patterns", []),
            architecture=data.get("architecture", "layered"),
            directory_structure=data.get("directory_structure", []),
            dependencies=data.get("dependencies", []),
            dev_dependencies=data.get("dev_dependencies", []),
            testing=data.get("testing", []),
            linting=data.get("linting", []),
            formatter=data.get("formatter", []),
            type_checker=data.get("type_checker", []),
            docker=data.get("docker", False),
            ci_cd=data.get("ci_cd", "none"),
            environment_variables=data.get("environment_variables", {}),
            quality_rules=data.get("quality_rules", []),
            documentation_strategy=data.get("documentation_strategy", "docstrings"),
            coding_conventions=data.get("coding_conventions", []),
            security_requirements=data.get("security_requirements", []),
            performance_requirements=data.get("performance_requirements", []),
            deployment_target=data.get("deployment_target", "docker"),
            decisions=decisions,
        )
