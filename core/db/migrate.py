"""Auto-migration on startup.

Runs Alembic migrations automatically when the application starts.
In development, runs `alembic upgrade head` at startup.
In production, also runs migrations before serving requests.
"""

from __future__ import annotations

import logging
import subprocess
import sys

from core.config import get_settings

logger = logging.getLogger(__name__)


def run_migrations() -> bool:
    """Run Alembic migrations to head.

    Returns:
        True if migrations succeeded or were already up-to-date.
        False if migrations failed.
    """
    try:
        logger.info("Running database migrations...")
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            if "Already at head" in result.stdout or result.stdout.strip() == "":
                logger.info("Database migrations: already up-to-date")
            else:
                logger.info("Database migrations applied successfully")
                logger.debug("Migration output: %s", result.stdout)
            return True
        else:
            logger.error("Migration failed (exit code %d)", result.returncode)
            logger.error("stderr: %s", result.stderr)
            return False

    except subprocess.TimeoutExpired:
        logger.error("Migration timed out after 60s")
        return False
    except FileNotFoundError:
        logger.warning("Alembic not found, skipping migrations")
        return True
    except Exception as e:
        logger.error("Migration error: %s", e)
        return False


def run_migrations_if_needed() -> bool:
    """Run migrations only in development or if AUTO_MIGRATE is set.

    Returns:
        True if migrations succeeded or were skipped.
    """
    settings = get_settings()

    # Always run in development, or if explicitly enabled
    if settings.ENVIRONMENT == "development":
        return run_migrations()

    # In production, check AUTO_MIGRATE env var
    import os
    if os.environ.get("AUTO_MIGRATE", "false").lower() in ("true", "1", "yes"):
        return run_migrations()

    logger.info("Skipping auto-migration in %s environment", settings.ENVIRONMENT)
    return True
