import pandas as pd

from datapilot.charts import select_chart
from datapilot.models import ChartSpec


def test_keeps_valid_model_chart() -> None:
    frame = pd.DataFrame({"category": ["A", "B"], "profit": [12.0, 18.0]})
    requested = ChartSpec(chart_type="bar", x="category", y="profit", title="Profit")

    assert select_chart(requested, frame, "Compare profit") == requested


def test_falls_back_to_bar_for_category_comparison() -> None:
    frame = pd.DataFrame({"category": ["A", "B"], "profit": [12.0, 18.0]})

    chart = select_chart(ChartSpec(), frame, "Compare profit by category")

    assert chart.chart_type == "bar"
    assert chart.x == "category"
    assert chart.y == "profit"


def test_falls_back_to_line_for_time_series() -> None:
    frame = pd.DataFrame({"month": ["2026-01", "2026-02"], "revenue": [10, 15]})

    chart = select_chart(ChartSpec(), frame, "Show the monthly revenue trend")

    assert chart.chart_type == "line"
    assert chart.x == "month"
    assert chart.y == "revenue"


def test_falls_back_to_scatter_for_relationship() -> None:
    frame = pd.DataFrame({"area": [900, 1200], "price": [70, 95]})

    chart = select_chart(ChartSpec(), frame, "How strongly are area and price related?")

    assert chart.chart_type == "scatter"
    assert chart.x == "area"
    assert chart.y == "price"


def test_rejects_chart_without_numeric_measure() -> None:
    frame = pd.DataFrame({"city": ["Pune", "Mumbai"], "segment": ["A", "B"]})

    chart = select_chart(
        ChartSpec(chart_type="bar", x="city", y="segment", title="Invalid"),
        frame,
        "Compare cities",
    )

    assert chart.chart_type == "none"
