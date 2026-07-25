"""Tests for ArtifactManager."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.agents.artifact_manager import ArtifactManager
from core.orchestrator.state import FileStatus, FileTask, ProjectPlan


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def artifact_mgr(tmp_workspace: Path) -> ArtifactManager:
    return ArtifactManager(str(tmp_workspace))


class TestArtifactManager:
    def test_init_creates_dirs(self, tmp_workspace: Path):
        ArtifactManager(str(tmp_workspace))
        assert (tmp_workspace / ".ai_artifacts").exists()
        assert (tmp_workspace / ".ai_artifacts" / "files").exists()
        assert (tmp_workspace / ".ai_artifacts" / "logs").exists()

    def test_save_file(self, artifact_mgr: ArtifactManager, tmp_workspace: Path):
        artifact_mgr.save_file("src/main.py", "print('hello')")
        content = (tmp_workspace / "src" / "main.py").read_text()
        assert content == "print('hello')"

    def test_load_file(self, artifact_mgr: ArtifactManager, tmp_workspace: Path):
        (tmp_workspace / "test.py").write_text("test content")
        content = artifact_mgr.load_file("test.py")
        assert content == "test content"

    def test_load_file_not_found(self, artifact_mgr: ArtifactManager):
        content = artifact_mgr.load_file("nonexistent.py")
        assert content is None

    def test_save_plan(self, artifact_mgr: ArtifactManager, tmp_workspace: Path):
        plan = ProjectPlan(
            project_name="test",
            project_description="A test",
            files=[FileTask(file_path="a.py", description="A")],
        )
        artifact_mgr.save_plan(plan)
        plan_path = tmp_workspace / ".ai_artifacts" / "project_plan.json"
        assert plan_path.exists()
        data = json.loads(plan_path.read_text())
        assert data["project_name"] == "test"
        assert len(data["files"]) == 1

    def test_save_file_status(self, artifact_mgr: ArtifactManager, tmp_workspace: Path):
        task = FileTask(file_path="src/main.py", description="Main")
        task.status = FileStatus.DONE
        artifact_mgr.save_file_status(task)
        status_path = tmp_workspace / ".ai_artifacts" / "files" / "src_main.py.json"
        assert status_path.exists()
        data = json.loads(status_path.read_text())
        assert data["status"] == "done"

    def test_save_generation_log(self, artifact_mgr: ArtifactManager, tmp_workspace: Path):
        artifact_mgr.save_generation_log("test.py", "generate", True)
        log_path = tmp_workspace / ".ai_artifacts" / "logs" / "generation.log"
        assert log_path.exists()
        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["file_path"] == "test.py"
        assert data["success"] is True

    def test_get_completed_files(self, artifact_mgr: ArtifactManager, tmp_workspace: Path):
        # Save some file statuses
        for name, status in [("a.py", FileStatus.DONE), ("b.py", FileStatus.PENDING)]:
            task = FileTask(file_path=name, description="test")
            task.status = status
            artifact_mgr.save_file_status(task)

        completed = artifact_mgr.get_completed_files()
        assert completed == ["a.py"]

    def test_get_summary(self, artifact_mgr: ArtifactManager, tmp_workspace: Path):
        for name, status in [("a.py", FileStatus.DONE), ("b.py", FileStatus.PENDING)]:
            task = FileTask(file_path=name, description="test")
            task.status = status
            artifact_mgr.save_file_status(task)

        summary = artifact_mgr.get_summary()
        assert summary["done"] == 1
        assert summary["pending"] == 1
