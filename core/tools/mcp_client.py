"""MCP client for agents to call tools via the MCP protocol.

Provides a thin wrapper that agents use instead of importing tool
functions directly. Supports two modes:
- In-process: calls the server directly (no subprocess overhead)
- Stdio: spawns the MCP server as a subprocess (for external clients)

Usage:
    from core.tools.mcp_client import MCPToolClient

    client = MCPToolClient()
    result = await client.call("read_file", {
        "file_path": "src/main.py",
        "workspace_path": "/tmp/my-workspace"
    })
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.types import Tool

from core.tools.mcp_server import MCP_TOOLS, _dispatch_tool

logger = logging.getLogger(__name__)


class MCPToolClient:
    """Client that calls MCP tools in-process.

    This avoids the overhead of subprocess communication while still
    going through the MCP dispatch layer. External clients (Claude Desktop,
    etc.) connect via stdio or SSE.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {t.name: t for t in MCP_TOOLS}

    async def list_tools(self) -> list[Tool]:
        """List all available MCP tools.

        Returns:
            List of Tool definitions.
        """
        return MCP_TOOLS

    async def call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Call an MCP tool by name.

        Args:
            tool_name: Name of the tool to call.
            arguments: Tool input arguments.

        Returns:
            Parsed JSON result from the tool.

        Raises:
            ValueError: If the tool name is unknown.
        """
        if tool_name not in self._tools:
            raise ValueError(
                f"Unknown MCP tool: {tool_name}. Available: {list(self._tools.keys())}"
            )

        result_json = await _dispatch_tool(tool_name, arguments)
        return json.loads(result_json)

    def get_tool_schema(self, tool_name: str) -> dict[str, Any]:
        """Get the JSON Schema for a specific tool's input.

        Args:
            tool_name: Name of the tool.

        Returns:
            JSON Schema dict.

        Raises:
            ValueError: If the tool name is unknown.
        """
        if tool_name not in self._tools:
            raise ValueError(f"Unknown MCP tool: {tool_name}")
        return self._tools[tool_name].inputSchema

    def get_all_schemas(self) -> dict[str, dict[str, Any]]:
        """Get JSON Schemas for all tools.

        Returns:
            Dict mapping tool name to its input JSON Schema.
        """
        return {name: tool.inputSchema for name, tool in self._tools.items()}
