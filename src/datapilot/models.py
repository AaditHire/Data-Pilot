from __future__ import annotations

from typing import Literal, TypedDict

from pydantic import BaseModel, Field


class AnalysisPlan(BaseModel):
    """The planner agent's explicit interpretation of a business question."""

    answerable: bool
    unanswerable_reason: str
    suggested_questions: list[str] = Field(max_length=3)
    business_question: str
    metric: str
    dimensions: list[str] = Field(default_factory=list)
    filters: list[str] = Field(default_factory=list)
    approach: list[str] = Field(max_length=6)
    assumptions: list[str] = Field(default_factory=list)


class SQLProposal(BaseModel):
    """A typed SQL proposal produced by the query agent."""

    sql: str
    rationale: str


class ChartSpec(BaseModel):
    chart_type: Literal["bar", "line", "scatter", "none"] = "none"
    x: str | None = None
    y: str | None = None
    title: str = "Analysis result"


class AnalysisNarrative(BaseModel):
    headline: str
    summary: str
    key_findings: list[str] = Field(min_length=1, max_length=5)
    caveats: list[str] = Field(default_factory=list, max_length=4)
    chart: ChartSpec = Field(default_factory=ChartSpec)


class TraceEvent(BaseModel):
    stage: str
    status: Literal["running", "success", "error"]
    duration_ms: int
    detail: str


class AnalysisState(TypedDict, total=False):
    question: str
    schema_context: str
    plan: AnalysisPlan
    sql: str
    sql_rationale: str
    attempts: int
    error: str | None
    columns: list[str]
    rows: list[dict]
    narrative: AnalysisNarrative
    traces: list[TraceEvent]


class AnalysisResult(BaseModel):
    question: str
    plan: AnalysisPlan
    sql: str
    columns: list[str]
    rows: list[dict]
    narrative: AnalysisNarrative
    traces: list[TraceEvent]
    attempts: int
