"""Models router - admin endpoints for model profile management."""

import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import get_db_session, verify_api_key
from core.schemas import (
    ModelCapability,
    ModelProfileCreate,
    ModelProfileResponse,
    ModelProfileUpdate,
)
from db.models import ModelProfile

router = APIRouter()


def _profile_to_response(profile: ModelProfile) -> ModelProfileResponse:
    """Convert an ORM ModelProfile to a Pydantic response."""
    caps = json.loads(profile.capabilities)
    return ModelProfileResponse(
        id=profile.id,
        provider=profile.provider,
        model_id=profile.model_id,
        display_name=profile.display_name,
        capabilities=[ModelCapability(c) for c in caps],
        cost_per_1k_input=profile.cost_per_1k_input,
        cost_per_1k_output=profile.cost_per_1k_output,
        max_context=profile.max_context,
        priority=profile.priority,
        enabled=profile.enabled,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.get(
    "/models",
    response_model=list[ModelProfileResponse],
    summary="List all model profiles",
)
async def list_models(
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db_session),
) -> list[ModelProfileResponse]:
    """List all model profiles, ordered by priority."""
    result = await db.execute(select(ModelProfile).order_by(ModelProfile.priority))
    profiles = result.scalars().all()
    return [_profile_to_response(p) for p in profiles]


@router.post(
    "/models",
    response_model=ModelProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new model profile",
)
async def create_model(
    model: ModelProfileCreate,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db_session),
) -> ModelProfileResponse:
    """Create a new model profile (INSERT into model_profiles).

    Adding a new model is a DB operation, not a code change.
    """
    profile = ModelProfile(
        id=str(uuid.uuid4()),
        provider=model.provider,
        model_id=model.model_id,
        display_name=model.display_name,
        capabilities=json.dumps([c.value for c in model.capabilities]),
        cost_per_1k_input=model.cost_per_1k_input,
        cost_per_1k_output=model.cost_per_1k_output,
        max_context=model.max_context,
        priority=model.priority,
        enabled=model.enabled,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(profile)
    await db.flush()

    return _profile_to_response(profile)


@router.patch(
    "/models/{model_id}",
    response_model=ModelProfileResponse,
    summary="Update a model profile",
)
async def update_model(
    model_id: str,
    update: ModelProfileUpdate,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db_session),
) -> ModelProfileResponse:
    """Update an existing model profile (PATCH)."""
    result = await db.execute(select(ModelProfile).where(ModelProfile.id == model_id))
    profile = result.scalar_one_or_none()

    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model profile '{model_id}' not found.",
        )

    update_data = update.model_dump(exclude_unset=True)
    for field_name, value in update_data.items():
        if field_name == "capabilities" and value is not None:
            setattr(
                profile,
                field_name,
                json.dumps([c.value for c in value]),
            )
        else:
            setattr(profile, field_name, value)

    profile.updated_at = datetime.utcnow()
    await db.flush()

    return _profile_to_response(profile)
