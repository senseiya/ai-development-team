"""GitHub integration tool for branches, commits, and Pull Requests.

Uses PyGithub for GitHub API interaction. Authentication is done via
a personal access token (GITHUB_TOKEN env var) or OAuth2 flow.
"""

from __future__ import annotations

import logging
import os

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class GitHubCreateBranchInput(BaseModel):
    """Input for creating a Git branch."""

    repo_owner: str = Field(..., min_length=1, description="Repository owner")
    repo_name: str = Field(..., min_length=1, description="Repository name")
    branch_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[a-zA-Z0-9._/-]+$",
        description="Name for the new branch",
    )
    base_branch: str = Field(default="main", description="Branch to branch from")


class GitHubCommitInput(BaseModel):
    """Input for committing files."""

    repo_owner: str = Field(..., min_length=1, description="Repository owner")
    repo_name: str = Field(..., min_length=1, description="Repository name")
    branch_name: str = Field(..., min_length=1, description="Branch to commit to")
    message: str = Field(..., min_length=1, description="Commit message")
    files: list[dict[str, str]] = Field(
        ...,
        min_length=1,
        description="List of {path, content} dicts for changed files",
    )


class GitHubCreatePRInput(BaseModel):
    """Input for creating a Pull Request."""

    repo_owner: str = Field(..., min_length=1, description="Repository owner")
    repo_name: str = Field(..., min_length=1, description="Repository name")
    head_branch: str = Field(..., description="Source branch")
    base_branch: str = Field(default="main", description="Target branch")
    title: str = Field(..., min_length=1, description="PR title")
    body: str = Field(default="", description="PR description (markdown)")


class GitHubBranchOutput(BaseModel):
    """Output for branch creation."""

    branch_name: str
    sha: str
    url: str


class GitHubCommitOutput(BaseModel):
    """Output for a commit."""

    sha: str
    message: str
    url: str
    files_changed: int


class GitHubPROutput(BaseModel):
    """Output for PR creation."""

    pr_number: int
    url: str
    title: str
    state: str


class GitHubTokenInput(BaseModel):
    """Input for OAuth2 token exchange."""

    code: str = Field(..., description="Authorization code from GitHub OAuth")
    client_id: str = Field(..., description="GitHub OAuth App client ID")
    client_secret: str = Field(..., description="GitHub OAuth App client secret")


class GitHubTokenOutput(BaseModel):
    """Output for OAuth2 token exchange."""

    access_token: str
    token_type: str
    scope: str


# ---------------------------------------------------------------------------
# GitHub API Client
# ---------------------------------------------------------------------------


class GitHubClient:
    """Thin wrapper around GitHub REST API using httpx."""

    def __init__(self, token: str | None = None) -> None:
        self._token = token or os.environ.get("GITHUB_TOKEN", "")
        self._headers = {
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            self._headers["Authorization"] = f"Bearer {self._token}"

    async def _request(
        self,
        method: str,
        path: str,
        json: dict | None = None,
    ) -> dict:
        """Make an authenticated request to GitHub API."""
        url = f"{GITHUB_API_BASE}/{path}"
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method,
                url,
                headers=self._headers,
                json=json,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def get_branch(self, owner: str, repo: str, branch: str) -> dict:
        """Get branch info including SHA."""
        return await self._request("GET", f"repos/{owner}/{repo}/branches/{branch}")

    async def create_branch(
        self,
        owner: str,
        repo: str,
        branch_name: str,
        base_branch: str,
    ) -> GitHubBranchOutput:
        """Create a new branch from a base branch."""
        base_info = await self.get_branch(owner, repo, base_branch)
        base_sha = base_info["commit"]["sha"]

        await self._request(
            "POST",
            f"repos/{owner}/{repo}/git/refs",
            json={
                "ref": f"refs/heads/{branch_name}",
                "sha": base_sha,
            },
        )

        branch_info = await self.get_branch(owner, repo, branch_name)
        logger.info("Created branch %s at %s", branch_name, branch_info["commit"]["sha"])

        return GitHubBranchOutput(
            branch_name=branch_name,
            sha=branch_info["commit"]["sha"],
            url=f"https://github.com/{owner}/{repo}/tree/{branch_name}",
        )

    async def create_commit(
        self,
        owner: str,
        repo: str,
        branch_name: str,
        message: str,
        files: list[dict[str, str]],
    ) -> GitHubCommitOutput:
        """Create a commit with multiple file changes via the tree API."""
        # Get the current commit SHA
        branch_info = await self.get_branch(owner, repo, branch_name)
        base_sha = branch_info["commit"]["sha"]

        # Create blobs for each file
        blobs = []
        for file_data in files:
            blob = await self._request(
                "POST",
                f"repos/{owner}/{repo}/git/blobs",
                json={
                    "content": file_data["content"],
                    "encoding": "utf-8",
                },
            )
            blobs.append(
                {
                    "path": file_data["path"],
                    "mode": "100644",
                    "type": "blob",
                    "sha": blob["sha"],
                }
            )

        # Create a tree
        tree = await self._request(
            "POST",
            f"repos/{owner}/{repo}/git/trees",
            json={"tree": blobs, "base_tree": base_sha},
        )

        # Create the commit
        commit = await self._request(
            "POST",
            f"repos/{owner}/{repo}/git/commits",
            json={
                "message": message,
                "tree": tree["sha"],
                "parents": [base_sha],
            },
        )

        # Update the branch reference
        await self._request(
            "PATCH",
            f"repos/{owner}/{repo}/git/refs/heads/{branch_name}",
            json={"sha": commit["sha"]},
        )

        logger.info("Created commit %s on %s", commit["sha"][:7], branch_name)

        return GitHubCommitOutput(
            sha=commit["sha"],
            message=message,
            url=f"https://github.com/{owner}/{repo}/commit/{commit['sha']}",
            files_changed=len(files),
        )

    async def create_pr(
        self,
        owner: str,
        repo: str,
        head_branch: str,
        base_branch: str,
        title: str,
        body: str,
    ) -> GitHubPROutput:
        """Create a Pull Request."""
        pr = await self._request(
            "POST",
            f"repos/{owner}/{repo}/pulls",
            json={
                "title": title,
                "head": head_branch,
                "base": base_branch,
                "body": body,
            },
        )

        logger.info("Created PR #%d: %s", pr["number"], title)

        return GitHubPROutput(
            pr_number=pr["number"],
            url=pr["html_url"],
            title=title,
            state=pr["state"],
        )


# ---------------------------------------------------------------------------
# OAuth2 token exchange
# ---------------------------------------------------------------------------


async def exchange_github_code(input_data: GitHubTokenInput) -> GitHubTokenOutput:
    """Exchange a GitHub OAuth2 authorization code for an access token.

    Args:
        input_data: OAuth2 code exchange parameters.

    Returns:
        GitHubTokenOutput with the access token.

    Raises:
        httpx.HTTPStatusError: If the token exchange fails.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://github.com/login/oauth/access_token",
            json={
                "client_id": input_data.client_id,
                "client_secret": input_data.client_secret,
                "code": input_data.code,
            },
            headers={"Accept": "application/json"},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()

    return GitHubTokenOutput(
        access_token=data["access_token"],
        token_type=data.get("token_type", "bearer"),
        scope=data.get("scope", ""),
    )


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


async def create_branch(input_data: GitHubCreateBranchInput) -> GitHubBranchOutput:
    """Create a branch via the GitHub API."""
    client = GitHubClient()
    return await client.create_branch(
        owner=input_data.repo_owner,
        repo=input_data.repo_name,
        branch_name=input_data.branch_name,
        base_branch=input_data.base_branch,
    )


async def create_commit(input_data: GitHubCommitInput) -> GitHubCommitOutput:
    """Create a commit via the GitHub API."""
    client = GitHubClient()
    return await client.create_commit(
        owner=input_data.repo_owner,
        repo=input_data.repo_name,
        branch_name=input_data.branch_name,
        message=input_data.message,
        files=input_data.files,
    )


async def create_pull_request(input_data: GitHubCreatePRInput) -> GitHubPROutput:
    """Create a Pull Request via the GitHub API."""
    client = GitHubClient()
    return await client.create_pr(
        owner=input_data.repo_owner,
        repo=input_data.repo_name,
        head_branch=input_data.head_branch,
        base_branch=input_data.base_branch,
        title=input_data.title,
        body=input_data.body,
    )
