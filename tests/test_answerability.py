import pytest

from datapilot import AgenticAnalyst, DataWorkspace, QuestionNotAnswerableError
from datapilot.models import AnalysisPlan
from datapilot.sample_data import build_sample_tables


class UnanswerableAnalyst(AgenticAnalyst):
    def _structured(self, schema, instructions, prompt):
        assert schema is AnalysisPlan
        return AnalysisPlan(
            answerable=False,
            unanswerable_reason="The dataset has housing fields, not product or order data.",
            suggested_questions=["Compare average price by location."],
            business_question="Which product category is most profitable?",
            metric="",
            dimensions=[],
            filters=[],
            approach=[],
            assumptions=[],
        )


def test_unanswerable_question_stops_before_sql() -> None:
    analyst = UnanswerableAnalyst(
        DataWorkspace(build_sample_tables()),
        client=object(),  # type: ignore[arg-type]
    )
    with pytest.raises(QuestionNotAnswerableError) as exc_info:
        analyst.analyze("Which product category is most profitable?")
    assert "housing fields" in exc_info.value.reason
    assert exc_info.value.suggestions == ["Compare average price by location."]
