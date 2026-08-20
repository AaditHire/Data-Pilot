from __future__ import annotations

import re
from pathlib import Path

import duckdb
import pandas as pd

from .guardrails import validate_read_only_sql


def safe_table_name(name: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", name).strip("_").lower()
    if not normalized:
        normalized = "dataset"
    if normalized[0].isdigit():
        normalized = f"table_{normalized}"
    return normalized


class DataWorkspace:
    """In-memory, read-only analytical workspace backed by DuckDB."""

    def __init__(self, tables: dict[str, pd.DataFrame]):
        if not tables:
            raise ValueError("At least one table is required.")
        self.connection = duckdb.connect(":memory:")
        self.tables: dict[str, pd.DataFrame] = {}
        for source_name, frame in tables.items():
            table_name = safe_table_name(source_name)
            unique_name = table_name
            suffix = 2
            while unique_name in self.tables:
                unique_name = f"{table_name}_{suffix}"
                suffix += 1
            clean_frame = frame.copy()
            clean_frame.columns = [safe_table_name(str(column)) for column in clean_frame.columns]
            self.tables[unique_name] = clean_frame
            self.connection.register(unique_name, clean_frame)

    @classmethod
    def from_paths(cls, paths: list[str | Path]) -> DataWorkspace:
        tables: dict[str, pd.DataFrame] = {}
        for raw_path in paths:
            path = Path(raw_path)
            if path.suffix.lower() == ".csv":
                frame = pd.read_csv(path)
            elif path.suffix.lower() in {".parquet", ".pq"}:
                frame = pd.read_parquet(path)
            else:
                raise ValueError(f"Unsupported file type: {path.suffix}")
            tables[path.stem] = frame
        return cls(tables)

    @property
    def table_names(self) -> set[str]:
        return set(self.tables)

    def schema_context(self, sample_rows: int = 3) -> str:
        sections: list[str] = []
        for name, frame in self.tables.items():
            column_lines = [f"- {column}: {dtype}" for column, dtype in frame.dtypes.items()]
            sample = frame.head(sample_rows).to_json(orient="records", date_format="iso")
            sections.append(
                f"TABLE {name} ({len(frame):,} rows)\n"
                + "\n".join(column_lines)
                + f"\nSample rows: {sample}"
            )
        return "\n\n".join(sections)

    def execute(self, sql: str, row_limit: int = 500) -> tuple[str, pd.DataFrame]:
        validated = validate_read_only_sql(sql, self.table_names)
        wrapped = f"SELECT * FROM ({validated}) AS agent_result LIMIT {int(row_limit)}"
        result = self.connection.execute(wrapped).fetchdf()
        return validated, result

    def profile(self) -> pd.DataFrame:
        records = []
        for table, frame in self.tables.items():
            for column in frame.columns:
                records.append(
                    {
                        "table": table,
                        "column": column,
                        "dtype": str(frame[column].dtype),
                        "rows": len(frame),
                        "missing": int(frame[column].isna().sum()),
                        "unique": int(frame[column].nunique(dropna=True)),
                    }
                )
        return pd.DataFrame(records)

