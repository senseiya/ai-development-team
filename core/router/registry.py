"""Model registry with seed data for the automatic router.

Seed data populates the model_profiles table with initial free-tier
models from OpenRouter and one Ollama fallback per capability.

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
# Lower priority = tried first. Ollama models have higher priority (tried last).
SEED_MODELS: list[dict] = [
    # --- code_generation ---
    {
        "provider": "openrouter",
        "model_id": "qwen/qwen-2.5-coder-32b-instruct:free",
        "display_name": "Qwen 2.5 Coder 32B (Free)",
        "capabilities": ["code_generation"],
        "cost_per_1k_input": 0.0,
        "cost_per_1k_output": 0.0,
        "max_context": 32768,
        "priority": 10,
    },
    {
        "provider": "ollama",
        "model_id": "qwen2.5-coder:7b",
        "display_name": "Qwen 2.5 Coder 7B (Local)",
        "capabilities": ["code_generation"],
        "cost_per_1k_input": 0.0,
        "cost_per_1k_output": 0.0,
        "max_context": 8192,
        "priority": 100,
    },
    # --- reasoning ---
    {
        "provider": "openrouter",
        "model_id": "qwen/qwen-2.5-72b-instruct:free",
        "display_name": "Qwen 2.5 72B Instruct (Free)",
        "capabilities": ["reasoning"],
        "cost_per_1k_input": 0.0,
        "cost_per_1k_output": 0.0,
        "max_context": 32768,
        "priority": 10,
    },
    {
        "provider": "ollama",
        "model_id": "qwen2.5-coder:7b",
        "display_name": "Qwen 2.5 Coder 7B (Local)",
        "capabilities": ["reasoning"],
        "cost_per_1k_input": 0.0,
        "cost_per_1k_output": 0.0,
        "max_context": 8192,
        "priority": 100,
    },
    # --- code_review ---
    {
        "provider": "openrouter",
        "model_id": "deepseek/deepseek-chat:free",
        "display_name": "DeepSeek Chat V3 (Free)",
        "capabilities": ["code_review"],
        "cost_per_1k_input": 0.0,
        "cost_per_1k_output": 0.0,
        "max_context": 65536,
        "priority": 10,
    },
    {
        "provider": "ollama",
        "model_id": "qwen2.5-coder:7b",
        "display_name": "Qwen 2.5 Coder 7B (Local)",
        "capabilities": ["code_review"],
        "cost_per_1k_input": 0.0,
        "cost_per_1k_output": 0.0,
        "max_context": 8192,
        "priority": 100,
    },
    # --- summarization ---
    {
        "provider": "openrouter",
        "model_id": "qwen/qwen-2.5-coder-7b-instruct:free",
        "display_name": "Qwen 2.5 Coder 7B Instruct (Free)",
        "capabilities": ["summarization"],
        "cost_per_1k_input": 0.0,
        "cost_per_1k_output": 0.0,
        "max_context": 32768,
        "priority": 10,
    },
    {
        "provider": "ollama",
        "model_id": "qwen2.5-coder:7b",
        "display_name": "Qwen 2.5 Coder 7B (Local)",
        "capabilities": ["summarization"],
        "cost_per_1k_input": 0.0,
        "cost_per_1k_output": 0.0,
        "max_context": 8192,
        "priority": 100,
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
