"""Coder Agent - generates code based on user requests.

In Phase 5, the CoderAgent writes generated files to the workspace
using the filesystem tool and tracks changes for the file_changes table.
"""

from __future__ import annotations

import json
import logging
import re

from core.agents.base import BaseAgent
from core.orchestrator.state import AgentState, FileDiff
from core.schemas import ModelCapability
from core.tools.filesystem_tool import FileWriteInput, write_file

logger = logging.getLogger(__name__)

CODER_SYSTEM_PROMPT = """You are an expert software developer. Your task is to generate
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
    tools: list[str] = ["filesystem", "sandbox_exec"]

    async def run(self, state: AgentState) -> AgentState:
        """Execute the coder agent.

        Generates code via LLM, then writes files to the workspace
        using the filesystem tool. Records file changes for tracking.

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
            plan_context = (
                "\n\nDevelopment plan:\n"
                + json.dumps(state["plan"], indent=2, ensure_ascii=False)
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
                system_prompt=CODER_SYSTEM_PROMPT,
                state=state,
            )

            state["generated_code"] = response.content
            self._update_tokens(state, response.tokens_used)
            state["model_used"] = response.model
            state["provider_used"] = response.provider

            # Parse the JSON response to extract files
            files = self._parse_files(response.content)

            if files and workspace_path:
                # Write files to workspace
                changes = []
                for file_data in files:
                    file_path = file_data.get("path", "")
                    file_content = file_data.get("content", "")

                    if not file_path or not file_content:
                        continue

                    try:
                        write_result = write_file(
                            FileWriteInput(
                                file_path=file_path,
                                content=file_content,
                                workspace_path=workspace_path,
                            )
                        )
                        changes.append(
                            FileDiff(
                                file_path=file_path,
                                action="created" if write_result.created else "modified",
                                content=file_content,
                                diff="",  # Computed later if needed
                            )
                        )
                        logger.info(
                            "Wrote file: %s (%d bytes)", file_path, write_result.bytes_written
                        )
                    except PermissionError as e:
                        logger.warning("Blocked write to %s: %s", file_path, e)
                        self._add_message(state, f"Blocked: {e}", "warning")

                state["files_changed"] = changes
                self._add_message(
                    state,
                    f"Wrote {len(changes)} files to workspace",
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
            lines = [l for l in lines if not l.strip().startswith("```")]
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
