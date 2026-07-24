"""Benchmark tests — measure MCP layer overhead vs direct tool calls.

Phase 6 acceptance criteria requires documenting the latency overhead
introduced by the MCP layer compared to direct function calls.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from core.tools.filesystem_tool import (
    FileDiffInput,
    FileReadInput,
    FileWriteInput,
    compute_diff,
    read_file,
    write_file,
)
from core.tools.mcp_client import MCPToolClient


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Create a workspace with a test file."""
    (tmp_path / "bench.py").write_text("x = 1\n" * 100)
    return tmp_path


class TestMCPOverheadBenchmark:
    """Measure and compare direct vs MCP tool call latency."""

    def test_write_file_direct_vs_mcp(self, workspace: Path) -> None:
        """Benchmark write_file: direct call vs MCP client."""
        # Direct call (sync)
        start = time.perf_counter()
        for i in range(100):
            write_file(FileWriteInput(
                file_path=f"bench_direct_{i}.py",
                content="x = 1\n" * 100,
                workspace_path=str(workspace),
            ))
        direct_ms = (time.perf_counter() - start) * 1000

        # MCP call (async)
        client = MCPToolClient()

        async def run_mcp() -> None:
            for i in range(100):
                await client.call("write_file", {
                    "file_path": f"bench_mcp_{i}.py",
                    "content": "x = 1\n" * 100,
                    "workspace_path": str(workspace),
                })

        start = time.perf_counter()
        asyncio.run(run_mcp())
        mcp_ms = (time.perf_counter() - start) * 1000

        overhead_pct = ((mcp_ms - direct_ms) / direct_ms * 100) if direct_ms > 0 else 0

        print("\nBenchmark: write_file (100 calls)")
        print(f"  Direct: {direct_ms:.1f}ms")
        print(f"  MCP:    {mcp_ms:.1f}ms")
        print(f"  Overhead: {overhead_pct:+.1f}%")

        # MCP overhead should be < 500% (generous for in-process)
        assert overhead_pct < 500, (
            f"MCP overhead too high: {overhead_pct:.1f}%"
        )

    def test_read_file_direct_vs_mcp(self, workspace: Path) -> None:
        """Benchmark read_file: direct call vs MCP client."""
        # Direct call (sync)
        start = time.perf_counter()
        for _ in range(100):
            read_file(FileReadInput(
                file_path="bench.py",
                workspace_path=str(workspace),
            ))
        direct_ms = (time.perf_counter() - start) * 1000

        # MCP call (async)
        client = MCPToolClient()

        async def run_mcp() -> None:
            for _ in range(100):
                await client.call("read_file", {
                    "file_path": "bench.py",
                    "workspace_path": str(workspace),
                })

        start = time.perf_counter()
        asyncio.run(run_mcp())
        mcp_ms = (time.perf_counter() - start) * 1000

        overhead_pct = ((mcp_ms - direct_ms) / direct_ms * 100) if direct_ms > 0 else 0

        print("\nBenchmark: read_file (100 calls)")
        print(f"  Direct: {direct_ms:.1f}ms")
        print(f"  MCP:    {mcp_ms:.1f}ms")
        print(f"  Overhead: {overhead_pct:+.1f}%")

        assert overhead_pct < 500, (
            f"MCP overhead too high: {overhead_pct:.1f}%"
        )

    def test_compute_diff_direct_vs_mcp(self) -> None:
        """Benchmark compute_diff: direct call vs MCP client."""
        # Direct call (sync)
        start = time.perf_counter()
        for _ in range(100):
            compute_diff(FileDiffInput(
                original="line1\nline2\nline3\n",
                modified="line1\nlineModified\nline3\n",
                file_path="test.py",
            ))
        direct_ms = (time.perf_counter() - start) * 1000

        # MCP call (async)
        client = MCPToolClient()

        async def run_mcp() -> None:
            for _ in range(100):
                await client.call("compute_diff", {
                    "original": "line1\nline2\nline3\n",
                    "modified": "line1\nlineModified\nline3\n",
                    "file_path": "test.py",
                })

        start = time.perf_counter()
        asyncio.run(run_mcp())
        mcp_ms = (time.perf_counter() - start) * 1000

        overhead_pct = ((mcp_ms - direct_ms) / direct_ms * 100) if direct_ms > 0 else 0

        print("\nBenchmark: compute_diff (100 calls)")
        print(f"  Direct: {direct_ms:.1f}ms")
        print(f"  MCP:    {mcp_ms:.1f}ms")
        print(f"  Overhead: {overhead_pct:+.1f}%")

        assert overhead_pct < 500, (
            f"MCP overhead too high: {overhead_pct:.1f}%"
        )
