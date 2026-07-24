"""Core tools for the AI Development Team platform.

Tools are standalone modules that agents can use to interact with
external systems (filesystem, Docker, GitHub, databases).

Each tool follows the contract defined in the mcp-tool-contract skill:
- Pydantic input/output schemas
- Snake_case naming
- Explicit docstrings
"""

from core.tools.db_tool import DBQueryInput, DBQueryOutput, execute_query, get_schema
from core.tools.filesystem_tool import (
    FileReadInput,
    FileReadOutput,
    FileWriteInput,
    FileWriteOutput,
    compute_diff,
    list_files,
    read_file,
    write_file,
)
from core.tools.github_tool import (
    GitHubBranchOutput,
    GitHubCommitOutput,
    GitHubCreateBranchInput,
    GitHubCreatePRInput,
    GitHubPROutput,
    create_branch,
    create_commit,
    create_pull_request,
)
from core.tools.sandbox_exec_tool import (
    SandboxExecInput,
    SandboxExecOutput,
    execute_in_sandbox,
)

__all__ = [
    # Filesystem
    "FileReadInput",
    "FileReadOutput",
    "FileWriteInput",
    "FileWriteOutput",
    "read_file",
    "write_file",
    "list_files",
    "compute_diff",
    # Sandbox
    "SandboxExecInput",
    "SandboxExecOutput",
    "execute_in_sandbox",
    # GitHub
    "GitHubCreateBranchInput",
    "GitHubBranchOutput",
    "GitHubCreatePRInput",
    "GitHubCommitOutput",
    "GitHubPROutput",
    "create_branch",
    "create_commit",
    "create_pull_request",
    # Database
    "DBQueryInput",
    "DBQueryOutput",
    "execute_query",
    "get_schema",
]
