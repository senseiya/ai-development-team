"""Artifact Manager - tracks file generation states and persists artifacts."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from core.orchestrator.state import FileStatus, FileTask, ProjectPlan

logger = logging.getLogger(__name__)


class ArtifactManager:
    """Manages file artifacts, tracking their state and persisting to disk."""

    def __init__(self, workspace_path: str) -> None:
        """Initialize ArtifactManager.

        Args:
            workspace_path: Root directory for the project.
        """
        self.workspace = Path(workspace_path)
        self.artifacts_dir = self.workspace / ".ai_artifacts"
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """Create artifact directories."""
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        (self.artifacts_dir / "files").mkdir(exist_ok=True)
        (self.artifacts_dir / "logs").mkdir(exist_ok=True)

    def save_file(self, file_path: str, content: str) -> None:
        """Persist a generated file to disk.

        Args:
            file_path: Relative path within workspace.
            content: File content to save.
        """
        full_path = self.workspace / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        logger.info("Saved artifact: %s (%d bytes)", file_path, len(content))

    def load_file(self, file_path: str) -> str | None:
        """Load a file from workspace.

        Args:
            file_path: Relative path within workspace.

        Returns:
            File content or None if not found.
        """
        full_path = self.workspace / file_path
        if full_path.exists():
            return full_path.read_text(encoding="utf-8")
        return None

    def save_plan(self, plan: ProjectPlan) -> None:
        """Persist the project plan to disk.

        Args:
            plan: The ProjectPlan to save.
        """
        plan_path = self.artifacts_dir / "project_plan.json"
        data = {
            "project_name": plan.project_name,
            "project_description": plan.project_description,
            "files": [
                {
                    "file_path": f.file_path,
                    "description": f.description,
                    "dependencies": f.dependencies,
                    "status": f.status.value,
                }
                for f in plan.files
            ],
        }
        plan_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info("Saved project plan with %d files", len(plan.files))

    def save_file_status(self, file_task: FileTask) -> None:
        """Save individual file task status.

        Args:
            file_task: The FileTask to save status for.
        """
        status_path = self.artifacts_dir / "files" / f"{file_task.file_path.replace('/', '_')}.json"
        data = {
            "file_path": file_task.file_path,
            "status": file_task.status.value,
            "error": file_task.error,
            "repair_attempts": file_task.repair_attempts,
        }
        status_path.parent.mkdir(parents=True, exist_ok=True)
        status_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def save_generation_log(
        self,
        file_path: str,
        action: str,
        success: bool,
        error: str | None = None,
    ) -> None:
        """Log a file generation attempt.

        Args:
            file_path: Path of the file.
            action: Action taken (generate, validate, repair).
            success: Whether the action succeeded.
            error: Error message if failed.
        """
        import datetime

        log_path = self.artifacts_dir / "logs" / "generation.log"
        entry = {
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "file_path": file_path,
            "action": action,
            "success": success,
            "error": error,
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def get_completed_files(self) -> list[str]:
        """Get list of successfully generated files.

        Returns:
            List of relative file paths that are DONE.
        """
        completed = []
        for status_file in (self.artifacts_dir / "files").glob("*.json"):
            try:
                data = json.loads(status_file.read_text(encoding="utf-8"))
                if data.get("status") == FileStatus.DONE.value:
                    completed.append(data.get("file_path", ""))
            except (json.JSONDecodeError, KeyError):
                continue
        return completed

    def get_summary(self) -> dict[str, int]:
        """Get summary of file statuses.

        Returns:
            Dictionary of status -> count.
        """
        counts: dict[str, int] = {}
        for status_file in (self.artifacts_dir / "files").glob("*.json"):
            try:
                data = json.loads(status_file.read_text(encoding="utf-8"))
                status = data.get("status", "unknown")
                counts[status] = counts.get(status, 0) + 1
            except (json.JSONDecodeError, KeyError):
                continue
        return counts
