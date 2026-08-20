from __future__ import annotations

import re

import sqlglot
from sqlglot import exp


class UnsafeQueryError(ValueError):
    """Raised when generated SQL violates the read-only policy."""


FORBIDDEN_NODES = (
    exp.Alter,
    exp.Create,
    exp.Delete,
    exp.Drop,
    exp.Insert,
    exp.Merge,
    exp.Update,
)


def validate_read_only_sql(sql: str, allowed_tables: set[str]) -> str:
    """Return normalized SQL after enforcing a single read-only DuckDB query."""

    cleaned = sql.strip().rstrip(";").strip()
    if not cleaned:
        raise UnsafeQueryError("The generated SQL is empty.")
    if ";" in cleaned:
        raise UnsafeQueryError("Only one SQL statement is allowed.")

    try:
        statements = sqlglot.parse(cleaned, read="duckdb")
    except sqlglot.errors.ParseError as exc:
        raise UnsafeQueryError(f"SQL could not be parsed: {exc}") from exc

    if len(statements) != 1:
        raise UnsafeQueryError("Only one SQL statement is allowed.")

    statement = statements[0]
    if not isinstance(statement, (exp.Select, exp.Union)):
        raise UnsafeQueryError("Only SELECT or WITH queries are allowed.")
    if any(statement.find(node_type) for node_type in FORBIDDEN_NODES):
        raise UnsafeQueryError("The query contains a write or DDL operation.")

    cte_names = {cte.alias_or_name.lower() for cte in statement.find_all(exp.CTE)}
    referenced = {
        table.name.lower()
        for table in statement.find_all(exp.Table)
        if table.name and table.name.lower() not in cte_names
    }
    unknown = referenced - {table.lower() for table in allowed_tables}
    if unknown:
        raise UnsafeQueryError(f"Unknown table(s): {', '.join(sorted(unknown))}")

    # Reject common file/network access functions even when hidden in a SELECT.
    forbidden_functions = ("read_csv", "read_json", "read_parquet", "httpfs", "sqlite_scan")
    lowered = re.sub(r"\s+", " ", cleaned.lower())
    if any(name in lowered for name in forbidden_functions):
        raise UnsafeQueryError("External file and network access are not allowed.")

    return statement.sql(dialect="duckdb")

