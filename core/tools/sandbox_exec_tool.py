"""Sandboxed command execution in ephemeral Docker containers.

This is the most security-critical component of the system. All LLM-generated
code MUST execute inside an isolated container with:
- No network access (or restricted)
- Read-only root filesystem (except the run workspace mount)
- CPU and memory limits
- Time limits (kill after timeout)
- No privilege escalation
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

import docker
from docker.errors import APIError, ImageNotFound
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from docker.models.containers import Container

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_IMAGE = "python:3.11-slim"
DEFAULT_TIMEOUT = 120  # seconds
DEFAULT_MEM_LIMIT = "256m"
DEFAULT_CPU_PERIOD = 100_000
DEFAULT_CPU_QUOTA = 50_000  # 0.5 CPU
MAX_OUTPUT_BYTES = 64 * 1024  # 64 KB


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class SandboxExecInput(BaseModel):
    """Input schema for sandbox command execution."""

    command: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="Shell command to execute inside the container",
    )
    workspace_path: str = Field(
        ...,
        description="Absolute path to the workspace directory to mount as /workspace",
    )
    timeout: int = Field(
        default=DEFAULT_TIMEOUT,
        ge=1,
        le=600,
        description="Max execution time in seconds",
    )
    mem_limit: str = Field(
        default=DEFAULT_MEM_LIMIT,
        description="Memory limit (Docker format, e.g. '256m', '1g')",
    )
    cpu_quota: int = Field(
        default=DEFAULT_CPU_QUOTA,
        ge=0,
        description="CPU quota (period=100000, quota=50000 = 0.5 CPU)",
    )
    network_disabled: bool = Field(
        default=True,
        description="Disable network access inside the container",
    )
    env: dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables to set inside the container",
    )


class SandboxExecOutput(BaseModel):
    """Output schema for sandbox command execution."""

    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    container_id: str | None = None
    execution_time_ms: float = 0.0


# ---------------------------------------------------------------------------
# Main execution function
# ---------------------------------------------------------------------------


def execute_in_sandbox(input_data: SandboxExecInput) -> SandboxExecOutput:
    """Execute a command inside an ephemeral Docker container.

    The container is created, runs the command, and is removed regardless
    of success/failure. Volumes are mounted read-write for the workspace.

    Args:
        input_data: Validated execution parameters.

    Returns:
        SandboxExecOutput with exit code, stdout, stderr, and metadata.

    Raises:
        RuntimeError: If Docker is not available or image pull fails.
    """
    start = time.monotonic()
    workspace = Path(input_data.workspace_path).resolve()

    if not workspace.exists():
        return SandboxExecOutput(
            exit_code=1,
            stdout="",
            stderr=f"Workspace path does not exist: {workspace}",
            execution_time_ms=0.0,
        )

    client = _get_docker_client()

    # Pull image if not present
    _ensure_image(client, input_data)

    container: Container | None = None
    timed_out = False

    try:
        # Create ephemeral container
        container = client.containers.create(
            image=DEFAULT_IMAGE,
            command=["sh", "-c", input_data.command],
            volumes={
                str(workspace): {
                    "bind": "/workspace",
                    "mode": "rw",
                }
            },
            working_dir="/workspace",
            detach=True,
            network_disabled=input_data.network_disabled,
            mem_limit=input_data.mem_limit,
            cpu_period=DEFAULT_CPU_PERIOD,
            cpu_quota=input_data.cpu_quota,
            # Security: drop all capabilities, no privilege escalation
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
            # Read-only root except /tmp and /workspace
            read_only=True,
            tmpfs={"/tmp": "size=64m"},
            # Use a non-root user if possible
            user="1000:1000",
            environment=input_data.env,
            labels={"ai-team-sandbox": "true", "ephemeral": "true"},
        )

        logger.info(
            "Sandbox container created: %s (image=%s, timeout=%ds)",
            container.short_id,
            DEFAULT_IMAGE,
            input_data.timeout,
        )

        # Start and wait with timeout
        container.start()
        result = container.wait(timeout=input_data.timeout)

        exit_code = result.get("StatusCode", -1)

        # Capture output (limit to MAX_OUTPUT_BYTES)
        stdout_bytes = container.logs(stdout=True, stderr=False)[:MAX_OUTPUT_BYTES]
        stderr_bytes = container.logs(stdout=False, stderr=True)[:MAX_OUTPUT_BYTES]

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")

        elapsed_ms = (time.monotonic() - start) * 1000

        return SandboxExecOutput(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            timed_out=timed_out,
            container_id=container.short_id,
            execution_time_ms=elapsed_ms,
        )

    except Exception as e:
        elapsed_ms = (time.monotonic() - start) * 1000

        # Check if container timed out
        if container:
            try:
                container.reload()
                if container.status == "running":
                    timed_out = True
                    container.kill()
            except Exception:
                pass

        if timed_out:
            return SandboxExecOutput(
                exit_code=-1,
                stdout="",
                stderr=f"Command timed out after {input_data.timeout}s",
                timed_out=True,
                container_id=container.short_id if container else None,
                execution_time_ms=elapsed_ms,
            )

        logger.error("Sandbox execution failed: %s", str(e))
        return SandboxExecOutput(
            exit_code=1,
            stdout="",
            stderr=f"Sandbox error: {e}",
            execution_time_ms=elapsed_ms,
        )

    finally:
        # Always remove the container
        if container:
            try:
                container.remove(force=True)
                logger.debug("Sandbox container %s removed", container.short_id)
            except Exception as cleanup_err:
                logger.warning("Failed to remove container: %s", cleanup_err)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_docker_client() -> docker.DockerClient:
    """Get a Docker client, raising RuntimeError if Docker is unavailable."""
    try:
        client = docker.from_env()
        client.ping()
        return client
    except Exception as e:
        raise RuntimeError(
            f"Docker is not available. Ensure Docker Desktop is running. Error: {e}"
        ) from e


def _ensure_image(client: docker.DockerClient, input_data: SandboxExecInput) -> None:
    """Ensure the Docker image exists, pulling if necessary."""
    try:
        client.images.get(DEFAULT_IMAGE)
    except ImageNotFound:
        logger.info("Pulling Docker image %s...", DEFAULT_IMAGE)
        try:
            client.images.pull(DEFAULT_IMAGE)
        except APIError as e:
            raise RuntimeError(f"Failed to pull image {DEFAULT_IMAGE}: {e}") from e
