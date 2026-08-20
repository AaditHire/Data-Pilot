from datapilot.sample_data import build_sample_tables
from datapilot.workspace import DataWorkspace, safe_table_name


def test_safe_table_names() -> None:
    assert safe_table_name("Sales Data (2025)") == "sales_data_2025"
    assert safe_table_name("123") == "table_123"


def test_workspace_executes_read_only_query() -> None:
    workspace = DataWorkspace(build_sample_tables())
    sql, result = workspace.execute(
        "SELECT COUNT(*) AS completed_orders FROM orders WHERE status = 'completed'"
    )
    assert "SELECT COUNT(*)" in sql
    assert result.loc[0, "completed_orders"] > 0


def test_profile_contains_every_column() -> None:
    tables = build_sample_tables()
    workspace = DataWorkspace(tables)
    assert len(workspace.profile()) == sum(len(frame.columns) for frame in tables.values())

