"""Shared Pydantic schemas for the AI Development Team platform."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ModelCapability(str, Enum):
    """Capabilities that agents can request from the Model Router."""

    REASONING = "reasoning"
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    SUMMARIZATION = "summarization"
    LONG_CONTEXT = "long_context"


# --- API Schemas ---


class TaskCreate(BaseModel):
    """Schema for creating a new task."""

    description: str = Field(..., min_length=1, max_length=10000)


class RunResponse(BaseModel):
    """Schema for run responses."""

    id: str
    task_description: str
    status: str
    generated_code: str | None = None
    tokens_used: int = 0
    created_at: datetime
    updated_at: datetime


class ErrorResponse(BaseModel):
    """Schema for error responses."""

    detail: str


# --- LLM Schemas ---


class LLMResponse(BaseModel):
    """Response from an LLM provider."""

    content: str
    model: str
    tokens_used: int = 0
    finish_reason: str | None = None


# --- Agent Schemas (MVP minimal) ---


class AgentMessage(BaseModel):
    """Message exchanged between agents."""

    agent_name: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# --- Database Model Schemas ---


class RunCreate(BaseModel):
    """Schema for creating a run in database."""

    id: str
    task_description: str
    status: str = "pending"


class RunUpdate(BaseModel):
    """Schema for updating a run in database."""

    status: str | None = None
    generated_code: str | None = None
    tokens_used: int | None = None
