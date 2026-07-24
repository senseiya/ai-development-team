"""Tests for the filesystem tool — read, write, list, diff, and path traversal prevention."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.tools.filesystem_tool import (
    FileDiffInput,
    FileListInput,
    FileReadInput,
    FileWriteInput,
    PathTraversalError,
    SymlinkEscapeError,
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
        with pytest.raises(PathTraversalError, match="blocked pattern"):
            write_file(
                FileWriteInput(
                    file_path="../etc/passwd",
                    content="evil",
                    workspace_path=str(workspace),
                )
            )

    def test_write_blocked_tilde(self, workspace: Path) -> None:
        with pytest.raises(PathTraversalError, match="blocked pattern"):
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
        with pytest.raises(PathTraversalError, match="blocked pattern"):
            read_file(
                FileReadInput(
                    file_path="../../etc/passwd",
                    workspace_path=str(workspace),
                )
            )

    def test_read_blocked_symlink_escape(self, tmp_path: Path) -> None:
        """Symlink pointing outside the workspace must be blocked.

        CI runs on Linux, but this test was also verified locally on Windows
        to ensure cross-platform correctness. A dynamic temp file is used
        instead of a hardcoded path like /etc/passwd to avoid OS-dependent
        behavior.
        """
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "safe.txt").write_text("safe")

        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        outside_file = outside_dir / "secret.txt"
        outside_file.write_text("secret content")

        # Create a symlink inside workspace pointing to file outside
        link = workspace / "escape_link"
        try:
            link.symlink_to(outside_file)
        except OSError:
            pytest.skip("Symlink creation requires admin privileges on Windows")

        with pytest.raises(SymlinkEscapeError):
            read_file(
                FileReadInput(
                    file_path="escape_link",
                    workspace_path=str(workspace),
                )
            )
        # The real file must NOT have been read
        assert not outside_file.read_text().startswith("safe")

    def test_read_symlink_inside_workspace_ok(self, tmp_path: Path) -> None:
        """Symlink pointing INSIDE the workspace must be allowed."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        target = workspace / "real.txt"
        target.write_text("real content")

        link = workspace / "link_to_real.txt"
        try:
            link.symlink_to(target)
        except OSError:
            pytest.skip("Symlink creation requires admin privileges on Windows")

        result = read_file(
            FileReadInput(
                file_path="link_to_real.txt",
                workspace_path=str(workspace),
            )
        )
        assert result.content == "real content"


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
