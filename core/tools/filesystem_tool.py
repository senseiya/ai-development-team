"""Filesystem tool for safe file I/O within a controlled workspace.

All operations are sandboxed to a single workspace directory. Path traversal
attacks (symlinks, ../, absolute paths) are explicitly blocked.
"""

from __future__ import annotations

import difflib
import logging
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Maximum file size for read/write operations (1 MB)
MAX_FILE_SIZE = 1 * 1024 * 1024

# Blocked path patterns (path traversal prevention)
_BLOCKED_PATTERNS = [
    "..",
    "~",
    "$",
    "\\",
]


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class FileReadInput(BaseModel):
    """Input for reading a file."""

    file_path: str = Field(
        ...,
        min_length=1,
        max_length=1024,
        description="Relative path to the file within the workspace",
    )
    workspace_path: str = Field(
        ...,
        description="Absolute path to the workspace root directory",
    )


class FileWriteInput(BaseModel):
    """Input for writing a file."""

    file_path: str = Field(
        ...,
        min_length=1,
        max_length=1024,
        description="Relative path to the file within the workspace",
    )
    content: str = Field(
        ...,
        max_length=10 * 1024 * 1024,
        description="Content to write to the file",
    )
    workspace_path: str = Field(
        ...,
        description="Absolute path to the workspace root directory",
    )


class FileListInput(BaseModel):
    """Input for listing files."""

    workspace_path: str = Field(
        ...,
        description="Absolute path to the workspace root directory",
    )
    pattern: str = Field(
        default="**/*",
        description="Glob pattern to match files (relative to workspace)",
    )


class FileDiffInput(BaseModel):
    """Input for computing a diff between two file versions."""

    original: str = Field(default="", description="Original file content")
    modified: str = Field(default="", description="Modified file content")
    file_path: str = Field(default="file", description="File path for label")


class FileReadOutput(BaseModel):
    """Output for reading a file."""

    content: str
    file_path: str
    size_bytes: int


class FileWriteOutput(BaseModel):
    """Output for writing a file."""

    file_path: str
    bytes_written: int
    created: bool


class FileListOutput(BaseModel):
    """Output for listing files."""

    files: list[str]


class FileDiffOutput(BaseModel):
    """Output for file diff."""

    diff: str
    file_path: str
    hunks: int


# ---------------------------------------------------------------------------
# Internal: path validation
# ---------------------------------------------------------------------------


def _validate_path(file_path: str, workspace_path: str) -> Path:
    """Resolve and validate that the file path stays within the workspace.

    This function prevents path traversal attacks by:
    1. Resolving symlinks
    2. Checking the resolved path starts with the workspace
    3. Blocking known dangerous patterns

    Args:
        file_path: The user-provided relative file path.
        workspace_path: The absolute workspace root.

    Returns:
        Resolved absolute Path if valid.

    Raises:
        PermissionError: If the path escapes the workspace or is invalid.
    """
    # Block dangerous patterns
    for pattern in _BLOCKED_PATTERNS:
        if pattern in file_path:
            raise PermissionError(
                f"Path contains blocked pattern '{pattern}': {file_path}"
            )

    workspace = Path(workspace_path).resolve()
    target = (workspace / file_path).resolve()

    # Verify the resolved target is within the workspace
    try:
        target.relative_to(workspace)
    except ValueError as exc:
        raise PermissionError(
            f"Path traversal detected: '{file_path}' resolves outside workspace. "
            f"Target: {target}, Workspace: {workspace}"
        ) from exc

    # Additional check: no symlink tricks
    if target.exists() and target.is_symlink():
        real_target = target.resolve()
        try:
            real_target.relative_to(workspace)
        except ValueError as exc:
            raise PermissionError(
                f"Symlink '{file_path}' points outside workspace: {real_target}"
            ) from exc

    return target


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def read_file(input_data: FileReadInput) -> FileReadOutput:
    """Read a file from the workspace.

    Args:
        input_data: Validated read parameters.

    Returns:
        FileReadOutput with file content and metadata.

    Raises:
        PermissionError: If path traversal is detected.
        FileNotFoundError: If file does not exist.
    """
    target = _validate_path(input_data.file_path, input_data.workspace_path)

    if not target.exists():
        raise FileNotFoundError(f"File not found: {input_data.file_path}")

    if not target.is_file():
        raise ValueError(f"Not a file: {input_data.file_path}")

    size = target.stat().st_size
    if size > MAX_FILE_SIZE:
        raise ValueError(
            f"File too large: {size} bytes (max {MAX_FILE_SIZE})"
        )

    content = target.read_text(encoding="utf-8")
    logger.info("Read file: %s (%d bytes)", input_data.file_path, size)

    return FileReadOutput(
        content=content,
        file_path=input_data.file_path,
        size_bytes=size,
    )


def write_file(input_data: FileWriteInput) -> FileWriteOutput:
    """Write a file to the workspace.

    Creates parent directories if they don't exist.

    Args:
        input_data: Validated write parameters.

    Returns:
        FileWriteOutput with write metadata.

    Raises:
        PermissionError: If path traversal is detected.
    """
    target = _validate_path(input_data.file_path, input_data.workspace_path)

    created = not target.exists()

    # Create parent directories
    target.parent.mkdir(parents=True, exist_ok=True)

    target.write_text(input_data.content, encoding="utf-8")
    bytes_written = target.stat().st_size

    logger.info(
        "Write file: %s (%d bytes, created=%s)",
        input_data.file_path,
        bytes_written,
        created,
    )

    return FileWriteOutput(
        file_path=input_data.file_path,
        bytes_written=bytes_written,
        created=created,
    )


def list_files(input_data: FileListInput) -> FileListOutput:
    """List files in the workspace matching a glob pattern.

    Args:
        input_data: List parameters with workspace path and pattern.

    Returns:
        FileListOutput with list of relative file paths.
    """
    workspace = Path(input_data.workspace_path).resolve()

    if not workspace.exists():
        return FileListOutput(files=[])

    files = []
    for p in sorted(workspace.glob(input_data.pattern)):
        if p.is_file():
            try:
                rel = p.relative_to(workspace)
                files.append(str(rel).replace("\\", "/"))
            except ValueError:
                continue

    return FileListOutput(files=files)


def compute_diff(input_data: FileDiffInput) -> FileDiffOutput:
    """Compute a unified diff between original and modified content.

    Args:
        input_data: Diff parameters.

    Returns:
        FileDiffOutput with the unified diff string.
    """
    original_lines = input_data.original.splitlines(keepends=True)
    modified_lines = input_data.modified.splitlines(keepends=True)

    diff = difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile=f"a/{input_data.file_path}",
        tofile=f"b/{input_data.file_path}",
    )

    diff_text = "".join(diff)
    hunks = diff_text.count("@@")

    return FileDiffOutput(
        diff=diff_text,
        file_path=input_data.file_path,
        hunks=hunks,
    )
