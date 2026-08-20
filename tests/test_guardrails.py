import pytest

from datapilot.guardrails import UnsafeQueryError, validate_read_only_sql

ALLOWED = {"orders", "customers"}


def test_allows_select_and_cte() -> None:
    sql = "WITH totals AS (SELECT customer_id, SUM(revenue) revenue FROM orders GROUP BY 1) SELECT * FROM totals"
    validated = validate_read_only_sql(sql, ALLOWED)
    assert "WITH totals" in validated


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM orders",
        "DROP TABLE orders",
        "SELECT * FROM secret_table",
        "SELECT * FROM read_csv('private.csv')",
        "SELECT 1; SELECT 2",
    ],
)
def test_blocks_unsafe_queries(sql: str) -> None:
    with pytest.raises(UnsafeQueryError):
        validate_read_only_sql(sql, ALLOWED)

