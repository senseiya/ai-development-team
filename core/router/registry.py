"""Model registry with seed data for the automatic router.

Seed data populates the model_profiles table with initial free-tier
models from OpenRouter.

To add a new model: INSERT into model_profiles — no code change needed.
"""

from __future__ import annotations

import json
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ModelProfile

logger = logging.getLogger(__name__)

# Seed data: list of dicts ready to insert as model_profiles rows.
# Lower priority = tried first.
SEED_MODELS: list[dict] = [
    # --- code_generation ---
    {
        "provider": "openrouter",
        "model_id": "google/gemma-4-26b-a4b-it:free",
        "display_name": "Google Gemma 4 26B (Free)",
        "capabilities": ["code_generation"],
        "cost_per_1k_input": 0.0,
        "cost_per_1k_output": 0.0,
        "max_context": 32768,
        "priority": 10,
    },
    # --- reasoning ---
    {
        "provider": "openrouter",
        "model_id": "google/gemma-4-31b-it:free",
        "display_name": "Google Gemma 4 31B (Free)",
        "capabilities": ["reasoning"],
        "cost_per_1k_input": 0.0,
        "cost_per_1k_output": 0.0,
        "max_context": 32768,
        "priority": 10,
    },
    # --- code_review ---
    {
        "provider": "openrouter",
        "model_id": "openai/gpt-oss-20b:free",
        "display_name": "OpenAI GPT-OSS 20B (Free)",
        "capabilities": ["code_review"],
        "cost_per_1k_input": 0.0,
        "cost_per_1k_output": 0.0,
        "max_context": 32768,
        "priority": 10,
    },
    # --- summarization ---
    {
        "provider": "openrouter",
        "model_id": "nvidia/nemotron-3-super-120b-a12b:free",
        "display_name": "NVIDIA Nemotron 3 Super 120B (Free)",
        "capabilities": ["summarization"],
        "cost_per_1k_input": 0.0,
        "cost_per_1k_output": 0.0,
        "max_context": 32768,
        "priority": 10,
    },
]


async def seed_model_profiles(db: AsyncSession) -> int:
    """Insert seed model profiles if the table is empty.

    Args:
        db: Async database session.

    Returns:
        Number of profiles inserted.
    """
    result = await db.execute(select(ModelProfile).limit(1))
    existing = result.scalar_one_or_none()

    if existing is not None:
        logger.info("model_profiles already populated, skipping seed.")
        return 0

    count = 0
    for data in SEED_MODELS:
        profile = ModelProfile(
            id=str(uuid.uuid4()),
            provider=data["provider"],
            model_id=data["model_id"],
            display_name=data["display_name"],
            capabilities=json.dumps(data["capabilities"]),
            cost_per_1k_input=data["cost_per_1k_input"],
            cost_per_1k_output=data["cost_per_1k_output"],
            max_context=data["max_context"],
            priority=data["priority"],
            enabled=True,
        )
        db.add(profile)
        count += 1

    await db.flush()
    logger.info("Seeded %d model profiles.", count)
    return count
