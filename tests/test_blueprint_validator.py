"""Tests for BlueprintValidator."""

from __future__ import annotations

import pytest

from core.orchestrator.state import ProjectBlueprint
from core.validators.blueprint_validator import BlueprintValidationError, BlueprintValidator


@pytest.fixture
def validator() -> BlueprintValidator:
    return BlueprintValidator()


# --- Valid combinations ---


class TestValidCombinations:
    def test_fastapi_sqlalchemy(self, validator):
        bp = ProjectBlueprint(backend="FastAPI", orm="SQLAlchemy", database="PostgreSQL")
        validator.validate(bp)  # should not raise

    def test_django_django_orm(self, validator):
        bp = ProjectBlueprint(backend="Django", orm="Django ORM", database="PostgreSQL")
        validator.validate(bp)

    def test_express_prisma(self, validator):
        bp = ProjectBlueprint(
            backend="Express", orm="Prisma", database="MongoDB",
            backend_language="typescript",
        )
        validator.validate(bp)

    def test_spring_hibernate(self, validator):
        bp = ProjectBlueprint(
            backend="Spring", orm="Hibernate", database="PostgreSQL",
            backend_language="python",
        )
        with pytest.raises(BlueprintValidationError) as exc:
            validator.validate(bp)
        assert "language" in str(exc.value).lower()

    def test_laravel_eloquent(self, validator):
        bp = ProjectBlueprint(
            backend="Laravel", orm="Eloquent", database="MySQL",
            backend_language="python",
        )
        with pytest.raises(BlueprintValidationError):
            validator.validate(bp)

    def test_gin_gorm(self, validator):
        bp = ProjectBlueprint(
            backend="Gin", orm="GORM", database="PostgreSQL",
            backend_language="go",
        )
        validator.validate(bp)

    def test_none_backend(self, validator):
        bp = ProjectBlueprint(backend="none", orm="none", database="none")
        validator.validate(bp)

    def test_html_frontend(self, validator):
        bp = ProjectBlueprint(
            backend="FastAPI", orm="none", frontend="HTML+CSS",
            frontend_language="none",
        )
        validator.validate(bp)

    def test_react_typescript(self, validator):
        bp = ProjectBlueprint(
            backend="FastAPI", orm="none", frontend="React",
            frontend_language="typescript",
        )
        validator.validate(bp)


# --- Invalid combinations ---


class TestInvalidCombinations:
    def test_fastapi_entity_framework(self, validator):
        bp = ProjectBlueprint(backend="FastAPI", orm="Entity Framework")
        with pytest.raises(BlueprintValidationError) as exc:
            validator.validate(bp)
        assert "not compatible with ORM" in str(exc.value)
        assert exc.value.category == "backend_orm"

    def test_fastapi_mongoose(self, validator):
        bp = ProjectBlueprint(backend="FastAPI", orm="Mongoose")
        with pytest.raises(BlueprintValidationError):
            validator.validate(bp)

    def test_fastapi_mongodb(self, validator):
        bp = ProjectBlueprint(backend="FastAPI", orm="SQLAlchemy", database="MongoDB")
        with pytest.raises(BlueprintValidationError):
            validator.validate(bp)

    def test_django_express_orm(self, validator):
        bp = ProjectBlueprint(backend="Django", orm="Prisma")
        with pytest.raises(BlueprintValidationError):
            validator.validate(bp)

    def test_express_sqlalchemy(self, validator):
        bp = ProjectBlueprint(backend="Express", orm="SQLAlchemy")
        with pytest.raises(BlueprintValidationError):
            validator.validate(bp)

    def test_wrong_language(self, validator):
        bp = ProjectBlueprint(backend="FastAPI", backend_language="go")
        with pytest.raises(BlueprintValidationError) as exc:
            validator.validate(bp)
        assert "language" in str(exc.value).lower() or "not compatible" in str(exc.value)

    def test_spring_gorm(self, validator):
        bp = ProjectBlueprint(backend="Spring", orm="GORM")
        with pytest.raises(BlueprintValidationError):
            validator.validate(bp)

    def test_laravel_sqlalchemy(self, validator):
        bp = ProjectBlueprint(backend="Laravel", orm="SQLAlchemy")
        with pytest.raises(BlueprintValidationError):
            validator.validate(bp)

    def test_frontend_html_wrong_language(self, validator):
        bp = ProjectBlueprint(frontend="HTML+CSS", frontend_language="typescript")
        with pytest.raises(BlueprintValidationError):
            validator.validate(bp)

    def test_react_none_language(self, validator):
        bp = ProjectBlueprint(frontend="React", frontend_language="none")
        with pytest.raises(BlueprintValidationError):
            validator.validate(bp)


# --- Unknown backend ---


class TestUnknownBackend:
    def test_unknown_backend(self, validator):
        bp = ProjectBlueprint(backend="NonexistentFramework")
        with pytest.raises(BlueprintValidationError) as exc:
            validator.validate(bp)
        assert "Unknown backend" in str(exc.value)
        assert exc.value.category == "backend"
