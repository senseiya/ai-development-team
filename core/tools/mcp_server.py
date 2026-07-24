"""MCP (Model Context Protocol) server exposing Phase 5 tools.

This server exposes filesystem, sandbox, GitHub, and database tools
via the standard MCP protocol, allowing any MCP-compatible client
(Claude Desktop, other agents, etc.) to use them.

Usage:
    python -m core.tools.mcp_server          # stdio mode (for CLI clients)
    python -m core.tools.mcp_server --sse    # SSE mode (for web clients)
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from core.tools.db_tool import (
    DBQueryInput,
    DBSchemaInput,
    execute_query,
    get_schema,
)
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
from core.tools.github_tool import (
    GitHubCreateBranchInput,
    GitHubCreatePRInput,
    GitHubTokenInput,
    create_branch,
    create_commit,
    create_pull_request,
    exchange_github_code,
)
from core.tools.sandbox_exec_tool import (
    SandboxExecInput,
    execute_in_sandbox,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MCP Tool definitions — JSON Schema for each tool's input
# ---------------------------------------------------------------------------

MCP_TOOLS: list[Tool] = [
    # --- Filesystem tools ---
    Tool(
        name="read_file",
        description="Read a file from the workspace. Prevents path traversal.",
        inputSchema=FileReadInput.model_json_schema(),
    ),
    Tool(
        name="write_file",
        description="Write a file to the workspace. Creates parent dirs. Prevents path traversal.",
        inputSchema=FileWriteInput.model_json_schema(),
    ),
    Tool(
        name="list_files",
        description="List files in the workspace matching a glob pattern.",
        inputSchema=FileListInput.model_json_schema(),
    ),
    Tool(
        name="compute_diff",
        description="Compute a unified diff between original and modified content.",
        inputSchema=FileDiffInput.model_json_schema(),
    ),
    # --- Sandbox tool ---
    Tool(
        name="execute_in_sandbox",
        description=(
            "Execute a command in an isolated Docker container. "
            "Network disabled, read-only root, CPU/memory limits."
        ),
        inputSchema=SandboxExecInput.model_json_schema(),
    ),
    # --- GitHub tools ---
    Tool(
        name="github_create_branch",
        description="Create a new Git branch from a base branch via GitHub API.",
        inputSchema=GitHubCreateBranchInput.model_json_schema(),
    ),
    Tool(
        name="github_create_commit",
        description="Create a commit with multiple file changes via GitHub API.",
        inputSchema={
            "type": "object",
            "properties": {
                "repo_owner": {"type": "string", "description": "Repository owner"},
                "repo_name": {"type": "string", "description": "Repository name"},
                "branch_name": {"type": "string", "description": "Branch to commit to"},
                "message": {"type": "string", "description": "Commit message"},
                "files": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "content": {"type": "string"},
                        },
                        "required": ["path", "content"],
                    },
                    "description": "List of {path, content} dicts",
                },
            },
            "required": ["repo_owner", "repo_name", "branch_name", "message", "files"],
        },
    ),
    Tool(
        name="github_create_pr",
        description="Create a Pull Request via GitHub API.",
        inputSchema=GitHubCreatePRInput.model_json_schema(),
    ),
    Tool(
        name="github_exchange_token",
        description="Exchange a GitHub OAuth2 authorization code for an access token.",
        inputSchema=GitHubTokenInput.model_json_schema(),
    ),
    # --- Database tools ---
    Tool(
        name="db_execute_query",
        description="Execute a read-only SQL query (SELECT/WITH/EXPLAIN only).",
        inputSchema=DBQueryInput.model_json_schema(),
    ),
    Tool(
        name="db_get_schema",
        description="Get database schema information (tables and columns).",
        inputSchema=DBSchemaInput.model_json_schema(),
    ),
]


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------


async def _dispatch_tool(name: str, arguments: dict[str, Any]) -> str:
    """Dispatch a tool call to the appropriate function.

    Args:
        name: Tool name.
        arguments: Tool input arguments.

    Returns:
        JSON string with the tool result.
    """
    try:
        if name == "read_file":
            result = read_file(FileReadInput(**arguments))
            return result.model_dump_json()

        elif name == "write_file":
            result = write_file(FileWriteInput(**arguments))
            return result.model_dump_json()

        elif name == "list_files":
            result = list_files(FileListInput(**arguments))
            return result.model_dump_json()

        elif name == "compute_diff":
            result = compute_diff(FileDiffInput(**arguments))
            return result.model_dump_json()

        elif name == "execute_in_sandbox":
            result = execute_in_sandbox(SandboxExecInput(**arguments))
            return result.model_dump_json()

        elif name == "github_create_branch":
            result = await create_branch(GitHubCreateBranchInput(**arguments))
            return result.model_dump_json()

        elif name == "github_create_commit":
            from core.tools.github_tool import GitHubCommitInput

            result = await create_commit(GitHubCommitInput(**arguments))
            return result.model_dump_json()

        elif name == "github_create_pr":
            result = await create_pull_request(GitHubCreatePRInput(**arguments))
            return result.model_dump_json()

        elif name == "github_exchange_token":
            result = await exchange_github_code(GitHubTokenInput(**arguments))
            return result.model_dump_json()

        elif name == "db_execute_query":
            result = await execute_query(DBQueryInput(**arguments))
            return result.model_dump_json()

        elif name == "db_get_schema":
            result = await get_schema(DBSchemaInput(**arguments))
            return result.model_dump_json()

        else:
            return json.dumps({"error": f"Unknown tool: {name}"})

    except Exception as e:
        logger.error("Tool %s failed: %s", name, e)
        return json.dumps({"error": str(e)})


# ---------------------------------------------------------------------------
# MCP Server setup
# ---------------------------------------------------------------------------


def create_mcp_server() -> Server:
    """Create and configure the MCP server with all tools.

    Returns:
        Configured MCP Server instance.
    """
    server = Server("ai-development-team")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """Return the list of available tools."""
        return MCP_TOOLS

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle a tool call from an MCP client."""
        result_json = await _dispatch_tool(name, arguments)
        return [TextContent(type="text", text=result_json)]

    return server


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def _run_stdio() -> None:
    """Run the MCP server over stdio."""
    server = create_mcp_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    """CLI entry point for the MCP server."""
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    asyncio.run(_run_stdio())


if __name__ == "__main__":
    main()
