"""Documentation Agent - generates documentation and creates Pull Requests.

In Phase 5, the DocumentationAgent:
1. Generates documentation via LLM
2. Creates a GitHub branch, commits code + docs, and opens a PR
"""

from __future__ import annotations

import logging

from core.agents.base import BaseAgent
from core.orchestrator.state import AgentState
from core.schemas import ModelCapability

logger = logging.getLogger(__name__)

DOCUMENTATION_SYSTEM_PROMPT = """You are a technical writer creating documentation for
newly generated code. Write clear, concise documentation.

Produce the following sections:
1. **Overview** — What the code does (1-2 sentences)
2. **Installation** — How to install dependencies (if applicable)
3. **Usage** — Code examples showing how to use the main functions/classes
4. **API Reference** — Brief description of each public function/class
5. **Notes** — Any caveats, limitations, or important design decisions

Guidelines:
- Write for developers who haven't seen the code
- Include type information in examples
- Keep it concise — no fluff
- Use markdown formatting
"""


class DocumentationAgent(BaseAgent):
    """Agent responsible for generating project documentation and PRs."""

    name = "documentation"
    capability = ModelCapability.SUMMARIZATION
    tools: list[str] = ["github"]

    async def run(self, state: AgentState) -> AgentState:
        """Execute the documentation agent.

        Generates documentation, then optionally creates a GitHub PR
        if github_tool is configured and a workspace is available.

        Args:
            state: Must contain 'generated_code' and 'user_request'.

        Returns:
            Updated AgentState with 'documentation' populated.
        """
        generated_code = state.get("generated_code", "")
        user_request = state.get("user_request", "")
        review_findings = state.get("review_findings", [])
        files_changed = state.get("files_changed", [])

        if not generated_code:
            state["documentation"] = "No code available to document."
            self._add_message(state, "No code to document", "warning")
            return state

        # Build context for the documentation agent
        findings_summary = ""
        if review_findings:
            findings_list = []
            for f in review_findings:
                findings_list.append(
                    f"- [{f.severity.value}] {f.category}: {f.description}"
                )
            findings_summary = (
                "\n\nReview findings to address in documentation:\n"
                + "\n".join(findings_list)
            )

        files_summary = ""
        if files_changed:
            files_list = [f"- {fc.file_path} ({fc.action})" for fc in files_changed]
            files_summary = "\n\nFiles changed:\n" + "\n".join(files_list)

        prompt = (
            f"Original request:\n{user_request}\n\n"
            f"Generated code:\n```python\n{generated_code}\n```"
            f"{findings_summary}{files_summary}\n\n"
            "Generate documentation for this code."
        )

        try:
            response = await self.call_llm(
                prompt=prompt,
                system_prompt=DOCUMENTATION_SYSTEM_PROMPT,
                state=state,
            )

            state["documentation"] = response.content
            state["status"] = "documenting"
            self._update_tokens(state, response.tokens_used)
            self._add_message(
                state,
                f"Documentation generated ({len(response.content)} chars)",
            )

            # Attempt to create PR if workspace and github config are available
            await self._try_create_pr(state)

            return state

        except Exception as e:
            logger.error("DocumentationAgent failed: %s", str(e))
            state["status"] = "failed"
            state["error"] = str(e)
            self._add_message(state, f"Documentation failed: {e}", "error")
            return state

    async def _try_create_pr(self, state: AgentState) -> None:
        """Attempt to create a GitHub PR with generated code and docs.

        This is best-effort: if GitHub is not configured, it silently skips.
        """
        from core.config import get_settings

        settings = get_settings()

        if not settings.GITHUB_TOKEN:
            self._add_message(
                state,
                "GitHub not configured — skipping PR creation",
                "info",
            )
            return

        try:
            from core.tools.github_tool import (
                GitHubClient,
            )

            # TODO: These should come from state/config in a real integration
            # For now, use placeholder values
            repo_owner = state.get("github_owner", "")
            repo_name = state.get("github_repo", "")

            if not repo_owner or not repo_name:
                self._add_message(
                    state,
                    "No GitHub repo configured — skipping PR creation",
                    "info",
                )
                return

            client = GitHubClient(token=settings.GITHUB_TOKEN)
            run_id = state.get("run_id", "unknown")
            branch_name = f"ai-dev/{run_id}"

            # Create branch
            branch = await client.create_branch(
                owner=repo_owner,
                repo=repo_name,
                branch_name=branch_name,
                base_branch="main",
            )
            self._add_message(
                state,
                f"Created branch: {branch.branch_name}",
            )

            # Prepare files for commit
            files_changed = state.get("files_changed", [])
            commit_files = []
            for fc in files_changed:
                if fc.content:
                    commit_files.append(
                        {"path": fc.file_path, "content": fc.content}
                    )

            # Add documentation file
            documentation = state.get("documentation", "")
            if documentation:
                commit_files.append(
                    {"path": "README.md", "content": documentation}
                )

            if not commit_files:
                self._add_message(state, "No files to commit", "warning")
                return

            # Commit
            commit = await client.create_commit(
                owner=repo_owner,
                repo=repo_name,
                branch_name=branch_name,
                message=f"feat: AI-generated code for run {run_id}",
                files=commit_files,
            )
            self._add_message(
                state,
                f"Committed {commit.files_changed} files: {commit.sha[:7]}",
            )

            # Create PR
            pr = await client.create_pr(
                owner=repo_owner,
                repo=repo_name,
                head_branch=branch_name,
                base_branch="main",
                title=f"AI Dev: {state.get('user_request', '')[:50]}",
                body=documentation[:4000] if documentation else "Auto-generated PR",
            )
            state["pr_url"] = pr.url
            self._add_message(
                state,
                f"PR created: {pr.url}",
            )

        except Exception as e:
            logger.warning("Failed to create PR: %s", e)
            self._add_message(state, f"PR creation failed: {e}", "warning")
