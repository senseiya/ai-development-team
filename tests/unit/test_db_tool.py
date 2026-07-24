"""Tests for the database tool — query validation and read-only enforcement."""

from __future__ import annotations

import pytest

from core.tools.db_tool import (
    _validate_read_only,
)


class TestQueryValidation:
    def test_select_query_allowed(self) -> None:
        _validate_read_only("SELECT * FROM users")

    def test_with_query_allowed(self) -> None:
        _validate_read_only("WITH cte AS (SELECT 1) SELECT * FROM cte")

    def test_explain_query_allowed(self) -> None:
        _validate_read_only("EXPLAIN SELECT * FROM users")

    def test_insert_blocked(self) -> None:
        with pytest.raises(PermissionError, match="Modifying"):
            _validate_read_only("INSERT INTO users VALUES (1)")

    def test_update_blocked(self) -> None:
        with pytest.raises(PermissionError, match="Modifying"):
            _validate_read_only("UPDATE users SET name = 'evil'")

    def test_delete_blocked(self) -> None:
        with pytest.raises(PermissionError, match="Modifying"):
            _validate_read_only("DELETE FROM users WHERE id = 1")

    def test_drop_blocked(self) -> None:
        with pytest.raises(PermissionError, match="Modifying"):
            _validate_read_only("DROP TABLE users")

    def test_create_table_blocked(self) -> None:
        with pytest.raises(PermissionError, match="Modifying"):
            _validate_read_only("CREATE TABLE evil (id INT)")

    def test_truncate_blocked(self) -> None:
        with pytest.raises(PermissionError, match="Modifying"):
            _validate_read_only("TRUNCATE TABLE users")

    def test_comment_bypass_blocked(self) -> None:
        """SQL injection via comments should be caught."""
        with pytest.raises(PermissionError, match="Modifying"):
            _validate_read_only("-- harmless\nDELETE FROM users")

    def test_block_comment_bypass_blocked(self) -> None:
        with pytest.raises(PermissionError, match="Modifying"):
            _validate_read_only("/* comment */ DROP TABLE users")

    def test_empty_query_blocked(self) -> None:
        with pytest.raises(PermissionError, match="Empty"):
            _validate_read_only("")

    def test_whitespace_only_blocked(self) -> None:
        with pytest.raises(PermissionError, match="Empty"):
            _validate_read_only("   \n  \t  ")
