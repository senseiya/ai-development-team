"""Coder Agent - generates code file by file.

In the incremental generation mode, the CoderAgent generates ONE file per call,
returning raw content without JSON wrapping. This enables syntax validation
and repair before moving to the next file.
"""

from __future__ import annotations

import json
import logging
import re

from core.agents.base import BaseAgent
from core.agents.context_builder import ContextBuilder
from core.orchestrator.state import AgentState, FileDiff, FileTask
from core.schemas import ModelCapability
from core.tools.mcp_client import MCPToolClient

logger = logging.getLogger(__name__)

CODER_SYSTEM_PROMPT_SINGLE = """You are an expert software developer. Generate ONLY the content
for a single file. Do not include any other files.

Guidelines:
- Write production-ready code
- Include proper error handling
- Follow language best practices
- Add docstrings to functions and classes
- Return ONLY the raw code content, no markdown, no JSON wrapping
"""

CODER_SYSTEM_PROMPT_MULTI = """You are an expert software developer. Your task is to generate
high-quality, clean, and well-documented code based on the user's request.

You MUST respond with a JSON object containing a "files" array. Each element has:
- "path": relative file path (e.g. "src/main.py")
- "content": the complete file content

Example:
{
  "files": [
    {"path": "src/calculator.py", "content": "class Calculator:\\n    ..."},
    {"path": "tests/test_calculator.py", "content": "import pytest\\n..."}
  ]
}

Guidelines:
- Write production-ready code
- Include proper error handling
- Follow Python best practices (PEP 8, type hints)
- Add docstrings to functions and classes
- Include test files when relevant
- Return ONLY valid JSON, no markdown fences
"""


class CoderAgent(BaseAgent):
    """Agent responsible for generating code from user requests."""

    name = "coder"
    capability = ModelCapability.CODE_GENERATION
    tools: list[str] = ["write_file", "list_files", "compute_diff"]

    def __init__(self) -> None:
        self._mcp = MCPToolClient()

    async def generate_file(
        self,
        file_task: FileTask,
        context_builder: ContextBuilder,
        state: AgentState,
    ) -> str | None:
        """Generate a single file.

        Args:
            file_task: The file task to generate.
            context_builder: Builds context for the file.
            state: Current AgentState.

        Returns:
            Generated content or None on failure.
        """
        file_context = context_builder.build_context(file_task)
        prompt = file_context.to_prompt()

        try:
            response = await self.call_llm(
                prompt=prompt,
                system_prompt=CODER_SYSTEM_PROMPT_SINGLE,
                state=state,
                temperature=0.2,
            )

            content = self._clean_response(response.content)
            self._update_tokens(state, response.tokens_used)
            state["model_used"] = response.model
            state["provider_used"] = response.provider

            logger.info(
                "Generated %s (%d bytes) using %s",
                file_task.file_path,
                len(content),
                response.model,
            )
            return content

        except Exception as e:
            logger.error("Failed to generate %s: %s", file_task.file_path, str(e))
            return None

    async def run(self, state: AgentState) -> AgentState:
        """Execute the coder agent (legacy mode - generates all files at once).

        For incremental generation, use generate_file() instead.

        Args:
            state: Must contain 'user_request' and optionally 'workspace_path'.

        Returns:
            Updated AgentState with generated files, diffs, and status.
        """
        user_request = state.get("user_request", "")
        workspace_path = state.get("workspace_path", "")

        if not user_request:
            state["status"] = "failed"
            state["error"] = "No user request provided"
            self._add_message(state, "No user request provided", "error")
            return state

        # Build context from plan if available
        plan_context = ""
        if state.get("plan"):
            plan_context = "\n\nDevelopment plan:\n" + json.dumps(
                state["plan"], indent=2, ensure_ascii=False
            )

        prompt = (
            f"Generate code for the following request:\n\n{user_request}"
            f"{plan_context}\n\n"
            "Return a JSON object with a 'files' array containing all files "
            "to create."
        )

        try:
            response = await self.call_llm(
                prompt=prompt,
                system_prompt=CODER_SYSTEM_PROMPT_MULTI,
                state=state,
            )

            state["generated_code"] = response.content
            self._update_tokens(state, response.tokens_used)
            state["model_used"] = response.model
            state["provider_used"] = response.provider

            # Parse the JSON response to extract files
            files = self._parse_files(response.content)

            if files and workspace_path:
                # Write files to workspace via MCP client
                changes = []
                for file_data in files:
                    file_path = file_data.get("path", "")
                    file_content = file_data.get("content", "")

                    if not file_path or not file_content:
                        continue

                    try:
                        result = await self._mcp.call(
                            "write_file",
                            {
                                "file_path": file_path,
                                "content": file_content,
                                "workspace_path": workspace_path,
                            },
                        )
                        created = result.get("created", True)
                        bytes_written = result.get("bytes_written", 0)
                        changes.append(
                            FileDiff(
                                file_path=file_path,
                                action="created" if created else "modified",
                                content=file_content,
                                diff="",
                            )
                        )
                        logger.info("MCP write_file: %s (%d bytes)", file_path, bytes_written)
                    except Exception as e:
                        logger.warning("MCP write_file failed for %s: %s", file_path, e)
                        self._add_message(state, f"Blocked: {e}", "warning")

                state["files_changed"] = changes
                self._add_message(
                    state,
                    f"Wrote {len(changes)} files to workspace via MCP",
                )
            elif files:
                # No workspace — store in state only
                state["files_changed"] = [
                    FileDiff(
                        file_path=f.get("path", ""),
                        action="created",
                        content=f.get("content", ""),
                        diff="",
                    )
                    for f in files
                    if f.get("path")
                ]

            state["status"] = "completed"
            self._add_message(
                state,
                f"Code generated using {response.model} ({response.provider})",
            )
            return state

        except Exception as e:
            logger.error("CoderAgent failed: %s", str(e))
            state["status"] = "failed"
            state["error"] = str(e)
            self._add_message(state, f"Coder failed: {e}", "error")
            return state

    def _clean_response(self, content: str) -> str:
        """Clean LLM response to extract just the code."""
        text = content.strip()

        # Strip markdown code blocks
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first line (```language)
            if lines:
                lines = lines[1:]
            # Remove last line (```)
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        return text.strip()

    def _parse_files(self, content: str) -> list[dict[str, str]]:
        """Parse LLM response to extract file list.

        Handles both raw JSON and markdown code blocks containing JSON.

        Args:
            content: LLM response content.

        Returns:
            List of {path, content} dicts.
        """
        text = content.strip()

        # Strip markdown code blocks if present
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [line for line in lines if not line.strip().startswith("```")]
            text = "\n".join(lines).strip()

        # Try to extract JSON
        json_match = re.search(r"\{[\s\S]*\"files\"[\s\S]*\}", text)
        if json_match:
            try:
                data = json.loads(json_match.group())
                files = data.get("files", [])
                if isinstance(files, list):
                    return [
                        {"path": f.get("path", ""), "content": f.get("content", "")}
                        for f in files
                        if isinstance(f, dict) and f.get("path")
                    ]
            except json.JSONDecodeError:
                pass

        # Fallback: treat entire content as a single Python file
        return [{"path": "main.py", "content": text}]
