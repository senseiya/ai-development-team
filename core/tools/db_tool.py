"""Database tool for read-only queries against project databases.

Used by the Planner agent to inspect database schemas and data
when generating code that interacts with databases. All queries
are read-only by design — no INSERT, UPDATE, DELETE, or DDL allowed.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# SQL statements that modify data — strictly forbidden
_MODIFYING_STATEMENTS = re.compile(
    r"^\s*(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)

# Maximum rows returned to prevent DoS
MAX_ROWS = 1000

# Maximum query length
MAX_QUERY_LENGTH = 10_000


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class DBQueryInput(BaseModel):
    """Input for executing a read-only SQL query."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=MAX_QUERY_LENGTH,
        description="SQL SELECT query to execute (read-only)",
    )
    database_url: str = Field(
        ...,
        description="Async SQLAlchemy database URL",
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Query parameters for parameterized queries",
    )
    limit: int = Field(
        default=MAX_ROWS,
        ge=1,
        le=MAX_ROWS,
        description="Maximum number of rows to return",
    )


class DBSchemaInput(BaseModel):
    """Input for getting database schema info."""

    database_url: str = Field(
        ...,
        description="Async SQLAlchemy database URL",
    )
    table_name: str | None = Field(
        default=None,
        description="Specific table to inspect (None for all tables)",
    )


class DBQueryOutput(BaseModel):
    """Output for database query execution."""

    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    truncated: bool


class DBSchemaOutput(BaseModel):
    """Output for database schema inspection."""

    tables: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Query validation
# ---------------------------------------------------------------------------


def _validate_read_only(query: str) -> None:
    """Ensure the query is read-only (SELECT or WITH only).

    Args:
        query: SQL query to validate.

    Raises:
        PermissionError: If the query modifies data.
    """
    # Strip comments and whitespace
    cleaned = query.strip()
    if cleaned.startswith("--"):
        # Remove single-line comments
        lines = cleaned.split("\n")
        cleaned = "\n".join(line for line in lines if not line.strip().startswith("--"))

    # Remove block comments
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL).strip()

    if not cleaned:
        raise PermissionError("Empty query after removing comments")

    # Check first meaningful keyword
    first_keyword = cleaned.split()[0].upper() if cleaned.split() else ""

    if first_keyword not in ("SELECT", "WITH", "EXPLAIN"):
        if _MODIFYING_STATEMENTS.match(cleaned):
            raise PermissionError(
                f"Modifying queries are not allowed: {first_keyword}..."
            )
        raise PermissionError(
            f"Only SELECT, WITH, and EXPLAIN queries are allowed. Got: {first_keyword}"
        )


# ---------------------------------------------------------------------------
# Query execution
# ---------------------------------------------------------------------------


async def execute_query(input_data: DBQueryInput) -> DBQueryOutput:
    """Execute a read-only SQL query.

    Args:
        input_data: Validated query parameters.

    Returns:
        DBQueryOutput with columns, rows, and metadata.

    Raises:
        PermissionError: If the query attempts to modify data.
        ValueError: If the database URL is invalid.
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    _validate_read_only(input_data.query)

    engine = create_async_engine(input_data.database_url)
    try:
        # Enforce LIMIT if not already present
        query = input_data.query.strip().rstrip(";")
        if "LIMIT" not in query.upper():
            query = f"{query} LIMIT {input_data.limit}"

        async with engine.connect() as conn:
            result = await conn.execute(text(query), input_data.params)
            columns = list(result.keys())
            rows_raw = result.fetchmany(input_data.limit + 1)
            truncated = len(rows_raw) > input_data.limit
            rows = [dict(zip(columns, row, strict=False)) for row in rows_raw[:input_data.limit]]

        logger.info("Query returned %d rows (truncated=%s)", len(rows), truncated)

        return DBQueryOutput(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            truncated=truncated,
        )
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Schema inspection
# ---------------------------------------------------------------------------


async def get_schema(input_data: DBSchemaInput) -> DBSchemaOutput:
    """Get database schema information (tables and columns).

    Args:
        input_data: Schema inspection parameters.

    Returns:
        DBSchemaOutput with table metadata.
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(input_data.database_url)
    try:
        async with engine.connect() as conn:
            # Get all tables
            tables_result = await conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' ORDER BY table_name"
                )
            )
            table_names = [row[0] for row in tables_result.fetchall()]

            if input_data.table_name:
                table_names = [
                    t for t in table_names if t == input_data.table_name
                ]

            tables = []
            for table_name in table_names:
                columns_result = await conn.execute(
                    text(
                        "SELECT column_name, data_type, is_nullable, "
                        "column_default "
                        "FROM information_schema.columns "
                        "WHERE table_name = :table_name AND table_schema = 'public' "
                        "ORDER BY ordinal_position"
                    ),
                    {"table_name": table_name},
                )
                columns = []
                for col in columns_result.fetchall():
                    columns.append(
                        {
                            "name": col[0],
                            "type": col[1],
                            "nullable": col[2] == "YES",
                            "default": col[3],
                        }
                    )

                tables.append({"name": table_name, "columns": columns})

        return DBSchemaOutput(tables=tables)
    finally:
        await engine.dispose()
