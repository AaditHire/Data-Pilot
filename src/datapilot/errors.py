from __future__ import annotations


class AnalysisError(RuntimeError):
    """Base class for failures that can be explained safely in the UI."""


class QuestionNotAnswerableError(AnalysisError):
    """Raised before SQL generation when the dataset cannot answer a question."""

    def __init__(self, reason: str, suggestions: list[str] | None = None):
        super().__init__(reason)
        self.reason = reason
        self.suggestions = suggestions or []


class StructuredOutputError(AnalysisError):
    """Raised when the provider repeatedly fails to honor a typed contract."""

