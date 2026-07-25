"""Context Builder - builds minimal context for each file to be generated.

Includes ProjectBlueprint information so the Coder never invents
frameworks, patterns, or architecture — everything comes from the Blueprint.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from core.orchestrator.state import FileTask, ProjectBlueprint, ProjectPlan

logger = logging.getLogger(__name__)


@dataclass
class FileContext:
    """Minimal context provided to Coder for generating a single file."""

    file_path: str
    description: str
    project_name: str
    project_description: str
    dependencies_content: dict[str, str] = field(default_factory=dict)
    dependency_interfaces: dict[str, str] = field(default_factory=dict)
    existing_files: list[str] = field(default_factory=list)
    blueprint: ProjectBlueprint | None = None

    def to_prompt(self) -> str:
        """Build a prompt string for the Coder agent."""
        sections = [
            f"Project: {self.project_name}",
            f"Description: {self.project_description}",
        ]

        # Add Blueprint rules — these are NON-NEGOTIABLE
        if self.blueprint:
            sections.append("")
            sections.append("=== ARCHITECTURE RULES (FOLLOW EXACTLY) ===")
            sections.append(f"Backend Framework: {self.blueprint.backend}")
            sections.append(f"Language: {self.blueprint.backend_language}")
            sections.append(f"Database: {self.blueprint.database}")
            sections.append(f"ORM: {self.blueprint.orm}")
            sections.append(f"Authentication: {self.blueprint.authentication}")
            sections.append(f"API Style: {self.blueprint.api_style}")
            sections.append(f"Architecture: {self.blueprint.architecture}")
            sections.append(f"Patterns: {', '.join(self.blueprint.patterns)}")
            sections.append(f"Docker: {'Yes' if self.blueprint.docker else 'No'}")
            if self.blueprint.testing:
                sections.append(f"Testing: {', '.join(self.blueprint.testing)}")
            if self.blueprint.linting:
                sections.append(f"Linting: {', '.join(self.blueprint.linting)}")
            if self.blueprint.coding_conventions:
                sections.append(
                    f"Conventions: {', '.join(self.blueprint.coding_conventions)}"
                )
            sections.append("=== END ARCHITECTURE RULES ===")

        sections.append("")
        sections.append(f"File to generate: {self.file_path}")
        sections.append(f"What this file should do: {self.description}")

        if self.existing_files:
            sections.append("")
            sections.append("Project structure (files created so far):")
            for f in self.existing_files:
                sections.append(f"  - {f}")

        if self.dependencies_content:
            sections.append("")
            sections.append("Dependencies (files this code imports from):")
            for dep_path, dep_content in self.dependencies_content.items():
                sections.append(f"\n--- {dep_path} ---")
                sections.append(dep_content)
                sections.append(f"--- end {dep_path} ---")

        if self.dependency_interfaces:
            sections.append("")
            sections.append("Interfaces from dependencies (types/classes to use):")
            for dep_path, iface in self.dependency_interfaces.items():
                sections.append(f"\n--- {dep_path} interface ---")
                sections.append(iface)
                sections.append(f"--- end {dep_path} interface ---")

        sections.append("")
        sections.append(
            "Generate ONLY the file content for this single file. "
            "Do not include any other files."
        )

        return "\n".join(sections)


class ContextBuilder:
    """Builds minimal context for each file to be generated.

    Includes ProjectBlueprint so the Coder follows the architecture exactly.
    """

    def __init__(
        self,
        project_plan: ProjectPlan,
        blueprint: ProjectBlueprint | None = None,
    ) -> None:
        self.plan = project_plan
        self.blueprint = blueprint

    def build_context(self, file_task: FileTask) -> FileContext:
        """Build context for a single file task.

        Includes:
        - ProjectBlueprint rules (non-negotiable)
        - The file's own description
        - Content of dependency files (already generated)
        - Interfaces from dependencies (extracted signatures)

        Args:
            file_task: The file task to build context for.

        Returns:
            FileContext with all relevant information.
        """
        # Get content of dependency files
        deps_content: dict[str, str] = {}
        deps_interfaces: dict[str, str] = {}

        for dep_path in file_task.dependencies:
            dep_task = self.plan.get_task(dep_path)
            if dep_task and dep_task.status.value == "done" and dep_task.content:
                deps_content[dep_path] = dep_task.content
                # Extract interface (first 50 lines or class/function signatures)
                deps_interfaces[dep_path] = self._extract_interface(dep_task.content)

        # List of all files created so far
        existing_files = [
            t.file_path
            for t in self.plan.files
            if t.status.value == "done" and t.file_path != file_task.file_path
        ]

        return FileContext(
            file_path=file_task.file_path,
            description=file_task.description,
            project_name=self.plan.project_name,
            project_description=self.plan.project_description,
            dependencies_content=deps_content,
            dependency_interfaces=deps_interfaces,
            existing_files=existing_files,
            blueprint=self.blueprint,
        )

    def _extract_interface(self, content: str) -> str:
        """Extract public interface from file content.

        Takes the first 50 lines as a reasonable approximation
        of the public interface (imports, class defs, function signatures).
        """
        lines = content.split("\n")
        interface_lines = []
        in_class = False
        class_indent = 0

        for line in lines:
            stripped = line.strip()

            # Track class definitions
            if stripped.startswith("class "):
                in_class = True
                class_indent = len(line) - len(line.lstrip())
                interface_lines.append(line)
                continue

            # If in class, only include method signatures (not bodies)
            if in_class:
                current_indent = len(line) - len(line.lstrip())
                if current_indent <= class_indent and stripped:
                    in_class = False
                elif (
                    stripped.startswith("def ")
                    or stripped.startswith("async def ")
                    or stripped.startswith("@")
                ):
                    interface_lines.append(line)
                    continue

            # Include imports, decorators, and top-level definitions
            if (
                stripped.startswith("import ")
                or stripped.startswith("from ")
                or stripped.startswith("def ")
                or stripped.startswith("async def ")
                or stripped.startswith("class ")
                or stripped.startswith("@")
                or stripped.startswith("__all__")
            ):
                interface_lines.append(line)

            if len(interface_lines) >= 50:
                break

        return "\n".join(interface_lines)
