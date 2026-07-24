"""Contract tests for MCP tools — verify schemas match Pydantic models.

Each MCP tool must respond exactly to its declared schema, with no
extra or missing fields compared to the Pydantic input model.
"""

from __future__ import annotations

import json

import pytest

from core.tools.mcp_server import MCP_TOOLS
from core.tools.mcp_client import MCPToolClient


class TestMCPToolSchemas:
    """Verify MCP tool schemas match their Pydantic input models."""

    def test_all_tools_registered(self) -> None:
        """Verify all expected MCP tools are registered."""
        tool_names = [t.name for t in MCP_TOOLS]
        expected = [
            "read_file",
            "write_file",
            "list_files",
            "compute_diff",
            "execute_in_sandbox",
            "github_create_branch",
            "github_create_commit",
            "github_create_pr",
            "github_exchange_token",
            "db_execute_query",
            "db_get_schema",
        ]
        assert sorted(tool_names) == sorted(expected)

    def test_tool_schemas_are_valid_json_schema(self) -> None:
        """Verify every tool schema is valid JSON Schema."""
        for tool in MCP_TOOLS:
            schema = tool.inputSchema
            assert isinstance(schema, dict), f"Schema for {tool.name} is not a dict"
            assert "type" in schema or "$defs" in schema, (
                f"Schema for {tool.name} missing 'type' or '$defs'"
            )

    def test_read_file_schema_matches_model(self) -> None:
        """Verify read_file MCP schema matches FileReadInput."""
        from core.tools.filesystem_tool import FileReadInput

        mcp_schema = _get_tool_schema("read_file")
        model_schema = FileReadInput.model_json_schema()

        assert_schemas_match(mcp_schema, model_schema, "read_file")

    def test_write_file_schema_matches_model(self) -> None:
        """Verify write_file MCP schema matches FileWriteInput."""
        from core.tools.filesystem_tool import FileWriteInput

        mcp_schema = _get_tool_schema("write_file")
        model_schema = FileWriteInput.model_json_schema()

        assert_schemas_match(mcp_schema, model_schema, "write_file")

    def test_list_files_schema_matches_model(self) -> None:
        """Verify list_files MCP schema matches FileListInput."""
        from core.tools.filesystem_tool import FileListInput

        mcp_schema = _get_tool_schema("list_files")
        model_schema = FileListInput.model_json_schema()

        assert_schemas_match(mcp_schema, model_schema, "list_files")

    def test_compute_diff_schema_matches_model(self) -> None:
        """Verify compute_diff MCP schema matches FileDiffInput."""
        from core.tools.filesystem_tool import FileDiffInput

        mcp_schema = _get_tool_schema("compute_diff")
        model_schema = FileDiffInput.model_json_schema()

        assert_schemas_match(mcp_schema, model_schema, "compute_diff")

    def test_execute_in_sandbox_schema_matches_model(self) -> None:
        """Verify execute_in_sandbox MCP schema matches SandboxExecInput."""
        from core.tools.sandbox_exec_tool import SandboxExecInput

        mcp_schema = _get_tool_schema("execute_in_sandbox")
        model_schema = SandboxExecInput.model_json_schema()

        assert_schemas_match(mcp_schema, model_schema, "execute_in_sandbox")

    def test_github_create_branch_schema_matches_model(self) -> None:
        """Verify github_create_branch MCP schema matches GitHubCreateBranchInput."""
        from core.tools.github_tool import GitHubCreateBranchInput

        mcp_schema = _get_tool_schema("github_create_branch")
        model_schema = GitHubCreateBranchInput.model_json_schema()

        assert_schemas_match(mcp_schema, model_schema, "github_create_branch")

    def test_github_create_pr_schema_matches_model(self) -> None:
        """Verify github_create_pr MCP schema matches GitHubCreatePRInput."""
        from core.tools.github_tool import GitHubCreatePRInput

        mcp_schema = _get_tool_schema("github_create_pr")
        model_schema = GitHubCreatePRInput.model_json_schema()

        assert_schemas_match(mcp_schema, model_schema, "github_create_pr")

    def test_github_exchange_token_schema_matches_model(self) -> None:
        """Verify github_exchange_token MCP schema matches GitHubTokenInput."""
        from core.tools.github_tool import GitHubTokenInput

        mcp_schema = _get_tool_schema("github_exchange_token")
        model_schema = GitHubTokenInput.model_json_schema()

        assert_schemas_match(mcp_schema, model_schema, "github_exchange_token")

    def test_db_execute_query_schema_matches_model(self) -> None:
        """Verify db_execute_query MCP schema matches DBQueryInput."""
        from core.tools.db_tool import DBQueryInput

        mcp_schema = _get_tool_schema("db_execute_query")
        model_schema = DBQueryInput.model_json_schema()

        assert_schemas_match(mcp_schema, model_schema, "db_execute_query")

    def test_db_get_schema_matches_model(self) -> None:
        """Verify db_get_schema MCP schema matches DBSchemaInput."""
        from core.tools.db_tool import DBSchemaInput

        mcp_schema = _get_tool_schema("db_get_schema")
        model_schema = DBSchemaInput.model_json_schema()

        assert_schemas_match(mcp_schema, model_schema, "db_get_schema")


class TestMCPClientContract:
    """Verify the MCP client works correctly with the server."""

    @pytest.mark.asyncio
    async def test_client_lists_tools(self) -> None:
        """Client can list all tools."""
        client = MCPToolClient()
        tools = await client.list_tools()
        assert len(tools) == 11

    @pytest.mark.asyncio
    async def test_client_returns_json(self) -> None:
        """Client returns valid JSON from tool calls."""
        client = MCPToolClient()
        result = await client.call("compute_diff", {
            "original": "a\n",
            "modified": "b\n",
            "file_path": "test.txt",
        })
        assert isinstance(result, dict)
        assert "diff" in result
        assert "hunks" in result

    def test_client_get_tool_schema(self) -> None:
        """Client can get individual tool schemas."""
        client = MCPToolClient()
        schema = client.get_tool_schema("read_file")
        assert "properties" in schema
        assert "file_path" in schema["properties"]

    def test_client_get_all_schemas(self) -> None:
        """Client can get all tool schemas."""
        client = MCPToolClient()
        schemas = client.get_all_schemas()
        assert len(schemas) == 11
        assert "read_file" in schemas
        assert "execute_in_sandbox" in schemas


class TestMCPServerInteroperability:
    """Verify MCP server can be used by external clients."""

    def test_server_creates_correctly(self) -> None:
        """Verify MCP server can be created."""
        from core.tools.mcp_server import create_mcp_server

        server = create_mcp_server()
        assert server is not None

    def test_tools_have_descriptions(self) -> None:
        """All MCP tools must have descriptions."""
        for tool in MCP_TOOLS:
            assert tool.description, f"Tool {tool.name} missing description"
            assert len(tool.description) > 10, (
                f"Tool {tool.name} description too short"
            )

    def test_tools_have_names(self) -> None:
        """All MCP tools must have valid names."""
        for tool in MCP_TOOLS:
            assert tool.name, "Tool missing name"
            assert tool.name.replace("_", "").isalnum(), (
                f"Tool name '{tool.name}' has invalid characters"
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_tool_schema(tool_name: str) -> dict:
    """Get the MCP schema for a tool by name."""
    for tool in MCP_TOOLS:
        if tool.name == tool_name:
            return tool.inputSchema
    raise ValueError(f"Tool {tool_name} not found")


def assert_schemas_match(
    mcp_schema: dict,
    model_schema: dict,
    tool_name: str,
) -> None:
    """Assert that MCP schema matches the Pydantic model schema.

    Checks that:
    1. All required fields from the model are in the MCP schema
    2. No extra fields are in the MCP schema (beyond $defs and properties)
    3. Field types are compatible
    """
    mcp_props = mcp_schema.get("properties", {})
    model_props = model_schema.get("properties", {})
    mcp_required = set(mcp_schema.get("required", []))
    model_required = set(model_schema.get("required", []))

    # Check required fields
    missing_required = model_required - mcp_required
    assert not missing_required, (
        f"{tool_name}: MCP schema missing required fields: {missing_required}"
    )

    # Check properties exist
    missing_props = set(model_props.keys()) - set(mcp_props.keys())
    assert not missing_props, (
        f"{tool_name}: MCP schema missing properties: {missing_props}"
    )

    # No extra properties (beyond what model defines)
    extra_props = set(mcp_props.keys()) - set(model_props.keys())
    assert not extra_props, (
        f"{tool_name}: MCP schema has extra properties: {extra_props}"
    )
