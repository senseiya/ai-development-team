"""BlueprintValidator — validates architectural compatibility.

Runs immediately after the Architect produces a ProjectBlueprint.
If any technology combination is invalid (e.g. FastAPI + Entity Framework),
the validator raises BlueprintValidationError and the pipeline stops.

Compatibility rules come from two sources:
1. Hardcoded maps (BACKEND_ORM_MAP, BACKEND_DATABASE_MAP, etc.) for
   stable, well-known compatibilities that never change.
2. The blueprint_options table metadata_json for evolving compatibilities.
"""

from __future__ import annotations

import logging

from core.orchestrator.state import ProjectBlueprint

logger = logging.getLogger(__name__)


# --- Hardcoded compatibility maps ---
# These are stable truths — FastAPI will never support Entity Framework.

BACKEND_ORM_MAP: dict[str, list[str]] = {
    "FastAPI": ["SQLAlchemy", "Prisma", "Tortoise", "none"],
    "Django": ["Django ORM", "none"],
    "Express": ["Prisma", "Mongoose", "TypeORM", "none"],
    "Spring": ["Hibernate", "JPA", "none"],
    "Laravel": ["Eloquent", "none"],
    "Gin": ["GORM", "none"],
    "Flask": ["SQLAlchemy", "Prisma", "Tortoise", "none"],
    "none": ["none"],
}

BACKEND_DATABASE_MAP: dict[str, list[str]] = {
    "FastAPI": ["PostgreSQL", "SQLite", "MongoDB", "MySQL", "none"],
    "Django": ["PostgreSQL", "SQLite", "MySQL", "none"],
    "Express": ["PostgreSQL", "MongoDB", "MySQL", "SQLite", "none"],
    "Spring": ["PostgreSQL", "MySQL", "MongoDB", "SQLite", "none"],
    "Laravel": ["PostgreSQL", "MySQL", "SQLite", "none"],
    "Gin": ["PostgreSQL", "MySQL", "SQLite", "none"],
    "Flask": ["PostgreSQL", "SQLite", "MongoDB", "MySQL", "none"],
    "none": ["none"],
}

BACKEND_LANGUAGE_MAP: dict[str, list[str]] = {
    "FastAPI": ["python"],
    "Django": ["python"],
    "Flask": ["python"],
    "Express": ["typescript", "javascript"],
    "Spring": ["java", "kotlin"],
    "Laravel": ["php"],
    "Gin": ["go"],
    "none": ["python", "typescript", "go", "rust", "javascript"],
}

ORM_DATABASE_MAP: dict[str, list[str]] = {
    "SQLAlchemy": ["PostgreSQL", "SQLite", "MySQL", "none"],
    "Django ORM": ["PostgreSQL", "SQLite", "MySQL", "none"],
    "Prisma": ["PostgreSQL", "MySQL", "SQLite", "MongoDB", "none"],
    "Mongoose": ["MongoDB", "none"],
    "TypeORM": ["PostgreSQL", "MySQL", "SQLite", "MongoDB", "none"],
    "Hibernate": ["PostgreSQL", "MySQL", "Oracle", "none"],
    "JPA": ["PostgreSQL", "MySQL", "Oracle", "none"],
    "Eloquent": ["PostgreSQL", "MySQL", "SQLite", "none"],
    "GORM": ["PostgreSQL", "MySQL", "SQLite", "none"],
    "Tortoise": ["PostgreSQL", "SQLite", "MySQL", "none"],
    "none": ["PostgreSQL", "SQLite", "MongoDB", "MySQL", "none"],
}

FRONTEND_LANGUAGE_MAP: dict[str, list[str]] = {
    "React": ["typescript", "javascript"],
    "Vue": ["typescript", "javascript"],
    "Svelte": ["typescript", "javascript"],
    "HTMX": ["none"],
    "HTML+CSS": ["none"],
    "none": ["none"],
}


class BlueprintValidationError(Exception):
    """Raised when blueprint validation fails.

    Attributes:
        message: Human-readable explanation of what combination is invalid.
        category: Which field category failed (e.g. "backend_orm").
        selected: The value that was selected.
        incompatible_with: The incompatible paired value.
    """

    def __init__(
        self,
        message: str,
        category: str = "",
        selected: str = "",
        incompatible_with: str = "",
    ) -> None:
        self.category = category
        self.selected = selected
        self.incompatible_with = incompatible_with
        super().__init__(message)


class BlueprintValidator:
    """Validates architectural compatibility of a ProjectBlueprint."""

    def validate(self, blueprint: ProjectBlueprint) -> None:
        """Validate all architectural compatibility rules.

        Args:
            blueprint: The ProjectBlueprint to validate.

        Raises:
            BlueprintValidationError: If any combination is invalid.
        """
        self._validate_backend_and_orm(blueprint)
        self._validate_backend_and_database(blueprint)
        self._validate_backend_and_language(blueprint)
        self._validate_orm_and_database(blueprint)
        self._validate_frontend_and_language(blueprint)
        logger.info(
            "Blueprint validation passed for %s (%s / %s)",
            blueprint.project_name,
            blueprint.backend,
            blueprint.orm,
        )

    def _validate_backend_and_orm(self, blueprint: ProjectBlueprint) -> None:
        """Validate backend/ORM compatibility."""
        allowed = BACKEND_ORM_MAP.get(blueprint.backend)
        if allowed is None:
            raise BlueprintValidationError(
                f"Unknown backend '{blueprint.backend}'. "
                f"Supported backends: {', '.join(sorted(BACKEND_ORM_MAP))}",
                category="backend",
                selected=blueprint.backend,
            )
        if blueprint.orm not in allowed:
            raise BlueprintValidationError(
                f"Backend '{blueprint.backend}' is not compatible with ORM "
                f"'{blueprint.orm}'. Compatible ORMs: {', '.join(allowed)}",
                category="backend_orm",
                selected=blueprint.orm,
                incompatible_with=blueprint.backend,
            )

    def _validate_backend_and_database(self, blueprint: ProjectBlueprint) -> None:
        """Validate backend/database compatibility."""
        allowed = BACKEND_DATABASE_MAP.get(blueprint.backend)
        if allowed and blueprint.database not in allowed:
            raise BlueprintValidationError(
                f"Backend '{blueprint.backend}' is not compatible with database "
                f"'{blueprint.database}'. Compatible databases: {', '.join(allowed)}",
                category="backend_database",
                selected=blueprint.database,
                incompatible_with=blueprint.backend,
            )

    def _validate_backend_and_language(self, blueprint: ProjectBlueprint) -> None:
        """Validate backend/language compatibility."""
        allowed = BACKEND_LANGUAGE_MAP.get(blueprint.backend)
        if allowed and blueprint.backend_language not in allowed:
            raise BlueprintValidationError(
                f"Backend '{blueprint.backend}' requires language(s) "
                f"{', '.join(allowed)}, not '{blueprint.backend_language}'",
                category="backend_language",
                selected=blueprint.backend_language,
                incompatible_with=blueprint.backend,
            )

    def _validate_orm_and_database(self, blueprint: ProjectBlueprint) -> None:
        """Validate ORM/database compatibility."""
        if blueprint.orm == "none" or blueprint.database == "none":
            return
        allowed = ORM_DATABASE_MAP.get(blueprint.orm)
        if allowed and blueprint.database not in allowed:
            raise BlueprintValidationError(
                f"ORM '{blueprint.orm}' is not compatible with database "
                f"'{blueprint.database}'. Compatible databases: {', '.join(allowed)}",
                category="orm_database",
                selected=blueprint.database,
                incompatible_with=blueprint.orm,
            )

    def _validate_frontend_and_language(self, blueprint: ProjectBlueprint) -> None:
        """Validate frontend/language compatibility."""
        allowed = FRONTEND_LANGUAGE_MAP.get(blueprint.frontend)
        if allowed and blueprint.frontend_language not in allowed:
            raise BlueprintValidationError(
                f"Frontend '{blueprint.frontend}' requires language(s) "
                f"{', '.join(allowed)}, not '{blueprint.frontend_language}'",
                category="frontend_language",
                selected=blueprint.frontend_language,
                incompatible_with=blueprint.frontend,
            )
