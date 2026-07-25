"""Tests for SyntaxValidator."""

from __future__ import annotations

import pytest

from core.agents.syntax_validator import SyntaxValidator


@pytest.fixture
def validator() -> SyntaxValidator:
    return SyntaxValidator()


class TestSyntaxValidator:
    def test_valid_python(self, validator):
        result = validator.validate("test.py", "def hello():\n    pass\n")
        assert result.is_valid is True
        assert result.language == "python"

    def test_invalid_python(self, validator):
        result = validator.validate("test.py", "def hello(\n    pass\n")
        assert result.is_valid is False
        assert result.language == "python"
        assert result.error_message is not None
        assert result.line_number is not None

    def test_valid_python_complex(self, validator):
        code = """from typing import List, Dict

class Calculator:
    def __init__(self):
        self.history: List[float] = []

    def add(self, a: float, b: float) -> float:
        result = a + b
        self.history.append(result)
        return result

    def get_history(self) -> List[float]:
        return self.history.copy()
"""
        result = validator.validate("calc.py", code)
        assert result.is_valid is True

    def test_unknown_extension(self, validator):
        result = validator.validate("file.xyz", "some content")
        assert result.is_valid is True
        assert result.language == "unknown"

    def test_python_syntax_error_details(self, validator):
        code = "def foo():\n    x = 1\n    y = 2\n    return x +\n"
        result = validator.validate("test.py", code)
        assert result.is_valid is False
        assert result.error_message is not None
