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


class AgentStepDetail(BaseModel):
    """Per-agent timing detail for run breakdown."""

    agent: str
    status: str = "completed"
    duration_s: float = 0.0
    tokens_used: int = 0
    provider: str = ""
    model: str = ""
    error: str | None = None


class RunDetailResponse(BaseModel):
    """Detailed run response with per-agent breakdown."""

    id: str
    task_description: str
    status: str
    generated_code: str | None = None
    tokens_used: int = 0
    created_at: datetime
    updated_at: datetime
    agents: list[AgentStepDetail] = []
    total_duration_s: float = 0.0
    pr_url: str | None = None


class ErrorResponse(BaseModel):
    """Schema for error responses."""

    detail: str


# --- LLM Schemas ---


class LLMResponse(BaseModel):
    """Response from an LLM provider."""

    content: str
    model: str
    provider: str = "unknown"
    tokens_used: int = 0
    finish_reason: str | None = None
    latency_ms: float | None = None


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


# --- Model Profile Schemas ---


class ModelProfileCreate(BaseModel):
    """Schema for creating a new model profile."""

    provider: str = Field(..., pattern=r"^(openrouter|ollama)$")
    model_id: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=100)
    capabilities: list[ModelCapability] = Field(..., min_length=1)
    cost_per_1k_input: float = Field(default=0.0, ge=0)
    cost_per_1k_output: float = Field(default=0.0, ge=0)
    max_context: int = Field(default=4096, gt=0)
    priority: int = Field(default=100, ge=1, le=1000)
    enabled: bool = True


class ModelProfileUpdate(BaseModel):
    """Schema for updating a model profile."""

    display_name: str | None = None
    capabilities: list[ModelCapability] | None = None
    cost_per_1k_input: float | None = Field(default=None, ge=0)
    cost_per_1k_output: float | None = Field(default=None, ge=0)
    max_context: int | None = Field(default=None, gt=0)
    priority: int | None = Field(default=None, ge=1, le=1000)
    enabled: bool | None = None


class ModelProfileResponse(BaseModel):
    """Schema for model profile responses."""

    id: str
    provider: str
    model_id: str
    display_name: str
    capabilities: list[ModelCapability]
    cost_per_1k_input: float
    cost_per_1k_output: float
    max_context: int
    priority: int
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
