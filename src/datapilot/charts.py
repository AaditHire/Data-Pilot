from __future__ import annotations

import pandas as pd

from .models import ChartSpec

RELATIONSHIP_TERMS = ("correlation", "relationship", "related", "versus", " vs ")
TIME_TERMS = ("trend", "monthly", "weekly", "daily", "over time", "by date")
TIME_COLUMN_TERMS = ("date", "time", "month", "week", "year", "quarter", "day")


def _numeric_columns(frame: pd.DataFrame) -> list[str]:
    return [
        str(column)
        for column in frame.columns
        if pd.api.types.is_numeric_dtype(frame[column])
        and not pd.api.types.is_bool_dtype(frame[column])
    ]


def _is_time_column(frame: pd.DataFrame, column: str) -> bool:
    return pd.api.types.is_datetime64_any_dtype(frame[column]) or any(
        term in column.lower() for term in TIME_COLUMN_TERMS
    )


def _is_valid_chart(spec: ChartSpec, frame: pd.DataFrame) -> bool:
    if spec.chart_type == "none" or spec.x is None or spec.y is None:
        return False
    if spec.x not in frame.columns or spec.y not in frame.columns:
        return False
    if spec.y not in _numeric_columns(frame):
        return False
    return spec.chart_type != "scatter" or spec.x in _numeric_columns(frame)


def select_chart(spec: ChartSpec, frame: pd.DataFrame, question: str) -> ChartSpec:
    """Validate the model's chart choice and provide a data-driven fallback."""
    if frame.empty or len(frame) < 2:
        return ChartSpec()

    if _is_valid_chart(spec, frame):
        return spec

    numeric = _numeric_columns(frame)
    if not numeric:
        return ChartSpec()

    lowered_question = f" {question.lower()} "
    if len(numeric) >= 2 and any(term in lowered_question for term in RELATIONSHIP_TERMS):
        return ChartSpec(
            chart_type="scatter",
            x=numeric[0],
            y=numeric[1],
            title=f"{numeric[1]} vs {numeric[0]}",
        )

    dimensions = [str(column) for column in frame.columns if str(column) not in numeric]
    if dimensions:
        x = dimensions[0]
        is_time_series = _is_time_column(frame, x) or any(
            term in lowered_question for term in TIME_TERMS
        )
        return ChartSpec(
            chart_type="line" if is_time_series else "bar",
            x=x,
            y=numeric[0],
            title=f"{numeric[0]} by {x}",
        )

    if len(numeric) >= 2:
        return ChartSpec(
            chart_type="scatter",
            x=numeric[0],
            y=numeric[1],
            title=f"{numeric[1]} vs {numeric[0]}",
        )

    return ChartSpec()
