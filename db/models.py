"""SQLAlchemy ORM models for the AI Development Team platform."""

from datetime import datetime

from sqlalchemy import Boolean, Float, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class Run(Base):
    """Represents a development run/task execution."""

    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    generated_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    tokens_used: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<Run(id={self.id!r}, status={self.status!r})>"


class ModelProfile(Base):
    """Model profile for the automatic model router.

    Each row represents an available model with its capabilities,
    cost, and priority for fallback chain ordering.
    """

    __tablename__ = "model_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    capabilities: Mapped[str] = mapped_column(Text, nullable=False)
    cost_per_1k_input: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cost_per_1k_output: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_context: Mapped[int] = mapped_column(Integer, nullable=False, default=4096)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<ModelProfile(id={self.id!r}, provider={self.provider!r}, "
            f"model_id={self.model_id!r})>"
        )
