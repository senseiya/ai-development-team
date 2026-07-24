"""Tests for the filesystem tool — read, write, list, diff, and path traversal prevention."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.tools.filesystem_tool import (
    FileDiffInput,
    FileListInput,
    FileReadInput,
    FileWriteInput,
    compute_diff,
    list_files,
    read_file,
    write_file,
)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Create a temporary workspace directory."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')")
    (tmp_path / "README.md").write_text("# Test Project")
    return tmp_path


class TestWriteFile:
    def test_write_creates_file(self, workspace: Path) -> None:
        result = write_file(
            FileWriteInput(
                file_path="src/new.py",
                content="print('new')",
                workspace_path=str(workspace),
            )
        )
        assert result.file_path == "src/new.py"
        assert result.bytes_written > 0
        assert result.created is True
        assert (workspace / "src" / "new.py").read_text() == "print('new')"

    def test_write_overwrites_existing(self, workspace: Path) -> None:
        result = write_file(
            FileWriteInput(
                file_path="README.md",
                content="# Updated",
                workspace_path=str(workspace),
            )
        )
        assert result.created is False
        assert (workspace / "README.md").read_text() == "# Updated"

    def test_write_creates_parent_dirs(self, workspace: Path) -> None:
        write_file(
            FileWriteInput(
                file_path="deep/nested/dir/file.py",
                content="x = 1",
                workspace_path=str(workspace),
            )
        )
        assert (workspace / "deep" / "nested" / "dir" / "file.py").exists()

    def test_write_blocked_dotdot(self, workspace: Path) -> None:
        with pytest.raises(PermissionError, match="blocked pattern"):
            write_file(
                FileWriteInput(
                    file_path="../etc/passwd",
                    content="evil",
                    workspace_path=str(workspace),
                )
            )

    def test_write_blocked_tilde(self, workspace: Path) -> None:
        with pytest.raises(PermissionError, match="blocked pattern"):
            write_file(
                FileWriteInput(
                    file_path="~/secret",
                    content="evil",
                    workspace_path=str(workspace),
                )
            )


class TestReadFile:
    def test_read_existing_file(self, workspace: Path) -> None:
        result = read_file(
            FileReadInput(
                file_path="README.md",
                workspace_path=str(workspace),
            )
        )
        assert result.content == "# Test Project"
        assert result.file_path == "README.md"
        assert result.size_bytes > 0

    def test_read_nonexistent_file(self, workspace: Path) -> None:
        with pytest.raises(FileNotFoundError):
            read_file(
                FileReadInput(
                    file_path="nope.txt",
                    workspace_path=str(workspace),
                )
            )

    def test_read_blocked_traversal(self, workspace: Path) -> None:
        with pytest.raises(PermissionError, match="blocked pattern"):
            read_file(
                FileReadInput(
                    file_path="../../etc/passwd",
                    workspace_path=str(workspace),
                )
            )

    def test_read_blocked_symlink_escape(self, workspace: Path) -> None:
        # Create a symlink pointing outside workspace
        # On Windows, symlinks require admin privileges — skip if not available
        link = workspace / "escape_link"
        try:
            link.symlink_to("/etc/passwd")
        except OSError:
            pytest.skip("Symlink creation requires admin privileges on Windows")
        with pytest.raises(PermissionError, match="Symlink"):
            read_file(
                FileReadInput(
                    file_path="escape_link",
                    workspace_path=str(workspace),
                )
            )


class TestListFiles:
    def test_list_all_files(self, workspace: Path) -> None:
        result = list_files(FileListInput(workspace_path=str(workspace)))
        assert "README.md" in result.files
        assert "src/main.py" in result.files

    def test_list_with_pattern(self, workspace: Path) -> None:
        result = list_files(FileListInput(workspace_path=str(workspace), pattern="*.md"))
        assert result.files == ["README.md"]

    def test_list_empty_workspace(self, tmp_path: Path) -> None:
        result = list_files(FileListInput(workspace_path=str(tmp_path)))
        assert result.files == []


class TestComputeDiff:
    def test_diff_with_changes(self) -> None:
        result = compute_diff(
            FileDiffInput(
                original="line1\nline2\n",
                modified="line1\nline3\n",
                file_path="test.py",
            )
        )
        assert "line2" in result.diff
        assert "line3" in result.diff
        assert result.hunks >= 1

    def test_diff_no_changes(self) -> None:
        result = compute_diff(
            FileDiffInput(
                original="same\n",
                modified="same\n",
                file_path="test.py",
            )
        )
        assert result.diff == ""
        assert result.hunks == 0
