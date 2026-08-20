import pytest

from datapilot import AgenticAnalyst, DataWorkspace
from datapilot.sample_data import build_sample_tables


def test_groq_is_the_default_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    analyst = AgenticAnalyst(DataWorkspace(build_sample_tables()), client=object())  # type: ignore[arg-type]
    assert analyst.provider == "groq"
    assert analyst.model == "openai/gpt-oss-20b"


def test_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="LLM_PROVIDER"):
        AgenticAnalyst(
            DataWorkspace(build_sample_tables()),
            provider="unknown",
            client=object(),  # type: ignore[arg-type]
        )
