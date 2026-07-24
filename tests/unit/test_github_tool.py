"""Tests for the GitHub tool — mocked API interactions."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.tools.github_tool import (
    GitHubClient,
    GitHubTokenInput,
    exchange_github_code,
)


class TestGitHubClient:
    @pytest.mark.asyncio
    async def test_create_branch(self) -> None:
        client = GitHubClient(token="fake-token")

        mock_branch_info = {"commit": {"sha": "abc123"}}
        mock_new_branch = {"commit": {"sha": "def456"}}

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            # get_branch for base, create ref, get_branch for new branch
            mock_request.side_effect = [mock_branch_info, MagicMock(), mock_new_branch]

            result = await client.create_branch(
                owner="test-owner",
                repo="test-repo",
                branch_name="ai-dev/test-run",
                base_branch="main",
            )

            assert result.branch_name == "ai-dev/test-run"
            assert result.sha == "def456"
            assert "test-owner/test-repo" in result.url

    @pytest.mark.asyncio
    async def test_create_commit(self) -> None:
        client = GitHubClient(token="fake-token")

        mock_branch = {"commit": {"sha": "base123"}}
        mock_blob = {"sha": "blob456"}
        mock_tree = {"sha": "tree789"}
        mock_commit = {"sha": "commit000"}
        mock_branch_after = {"commit": {"sha": "commit000"}}

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = [
                mock_branch,   # get_branch
                mock_blob,     # create blob 1
                mock_tree,     # create tree
                mock_commit,   # create commit
                MagicMock(),   # update ref
                mock_branch_after,  # get_branch for sha
            ]

            result = await client.create_commit(
                owner="test-owner",
                repo="test-repo",
                branch_name="ai-dev/test-run",
                message="feat: AI-generated code",
                files=[{"path": "main.py", "content": "print('hello')"}],
            )

            assert result.sha == "commit000"
            assert result.files_changed == 1

    @pytest.mark.asyncio
    async def test_create_pr(self) -> None:
        client = GitHubClient(token="fake-token")

        mock_pr = {
            "number": 42,
            "html_url": "https://github.com/test-owner/test-repo/pull/42",
            "title": "AI Dev: test",
            "state": "open",
        }

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_pr

            result = await client.create_pr(
                owner="test-owner",
                repo="test-repo",
                head_branch="ai-dev/test-run",
                base_branch="main",
                title="AI Dev: test",
                body="## Overview\nGenerated code",
            )

            assert result.pr_number == 42
            assert result.state == "open"


class TestGitHubTokenExchange:
    @pytest.mark.asyncio
    async def test_exchange_code(self) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "gho_fake_token",
            "token_type": "bearer",
            "scope": "repo",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("core.tools.github_tool.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_client

            result = await exchange_github_code(
                GitHubTokenInput(
                    code="auth_code_123",
                    client_id="fake_client_id",
                    client_secret="fake_secret",
                )
            )

            assert result.access_token == "gho_fake_token"
            assert result.scope == "repo"
