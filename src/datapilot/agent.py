from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from typing import TypeVar

from dotenv import load_dotenv
from openai import BadRequestError, OpenAI
from pydantic import BaseModel

from .charts import select_chart
from .errors import QuestionNotAnswerableError, StructuredOutputError
from .models import (
    AnalysisNarrative,
    AnalysisPlan,
    AnalysisResult,
    AnalysisState,
    SQLProposal,
    TraceEvent,
)
from .workspace import DataWorkspace

T = TypeVar("T", bound=BaseModel)

PLANNER_PROMPT = """You are the planning specialist in an agentic data analyst.
First decide whether the business question can be answered using only the supplied tables and columns.
Do not reinterpret an unrelated question to make it fit the data and never invent columns.
If required data is missing, set answerable to false, explain the mismatch in one short sentence,
set metric and business_question to empty strings, set dimensions, filters, approach, and assumptions to
empty lists, and suggest up to three useful questions that are answerable from real columns.
If it is answerable, set answerable to true, leave unanswerable_reason and suggested_questions empty,
then create a concise analysis plan and call out assumptions explicitly.
Always return every schema field, even when its value is empty. Do not write SQL."""

SQL_PROMPT = """You are the SQL specialist in an agentic data analyst.
Write exactly one read-only DuckDB SELECT query that answers the plan.
Use only tables and columns in the schema. Prefer explicit aliases and robust aggregations.
Never use external file functions, DDL, DML, PRAGMA, ATTACH, COPY, EXPORT, or INSTALL.
The executor will apply a final row limit."""

REVIEWER_PROMPT = """You are the senior analytics reviewer in an agentic data analyst.
Explain only what is supported by the query result. Keep numbers precise, flag limitations, and avoid causal claims.
Recommend a bar chart for category comparisons, a line chart for time trends, or a scatter chart for relationships.
Use chart type none only when the result has fewer than two rows or no meaningful numeric comparison.
The chart x and y must exactly match result column names."""


class AgenticAnalyst:
    """Plan, generate, validate, repair, execute, and explain an analysis request."""

    def __init__(
        self,
        workspace: DataWorkspace,
        model: str | None = None,
        provider: str | None = None,
        client: OpenAI | None = None,
        max_attempts: int = 3,
    ):
        load_dotenv(".env.local")
        self.workspace = workspace
        self.provider = (provider or os.getenv("LLM_PROVIDER", "groq")).lower()
        if self.provider not in {"groq", "openai"}:
            raise ValueError("LLM_PROVIDER must be either 'groq' or 'openai'.")

        if self.provider == "groq":
            api_key = os.getenv("GROQ_API_KEY")
            if client is None and not api_key:
                raise ValueError(
                    "GROQ_API_KEY is missing. Run scripts\\save_groq_key.ps1, then restart the app."
                )
            self.model = model or os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
            self.client = client or OpenAI(
                api_key=api_key,
                base_url="https://api.groq.com/openai/v1",
            )
        else:
            self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
            self.client = client or OpenAI()
        self.max_attempts = max_attempts

    def _structured(self, schema: type[T], instructions: str, prompt: str) -> T:
        current_instructions = instructions
        for attempt in range(2):
            try:
                response = self.client.chat.completions.parse(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": current_instructions},
                        {"role": "user", "content": prompt},
                    ],
                    response_format=schema,
                )
                parsed = response.choices[0].message.parsed
                if parsed is None:
                    raise StructuredOutputError(
                        "The model did not return a valid structured response."
                    )
                return parsed
            except BadRequestError as exc:
                if getattr(exc, "code", None) not in {
                    "output_parse_failed",
                    "json_validate_failed",
                }:
                    raise
                if attempt == 0:
                    current_instructions += (
                        "\nReturn only one JSON object matching the required schema. "
                        "Include every required field, using empty strings or lists where appropriate. "
                        "Do not include analysis, markdown, or text outside the JSON object."
                    )
                    continue
                raise StructuredOutputError(
                    "The model could not produce the required structured response after a retry."
                ) from exc
        raise StructuredOutputError("The model could not produce a structured response.")

    @staticmethod
    def _trace(
        traces: list[TraceEvent], stage: str, operation: Callable[[], T]
    ) -> T:
        started = time.perf_counter()
        try:
            result = operation()
        except Exception as exc:
            traces.append(
                TraceEvent(
                    stage=stage,
                    status="error",
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    detail=str(exc)[:240],
                )
            )
            raise
        traces.append(
            TraceEvent(
                stage=stage,
                status="success",
                duration_ms=int((time.perf_counter() - started) * 1000),
                detail="Completed successfully",
            )
        )
        return result

    def analyze(self, question: str) -> AnalysisResult:
        question = question.strip()
        if len(question) < 5:
            raise ValueError("Please ask a more specific business question.")

        state: AnalysisState = {
            "question": question,
            "schema_context": self.workspace.schema_context(),
            "attempts": 0,
            "traces": [],
        }
        traces = state["traces"]

        state["plan"] = self._trace(
            traces,
            "Planner agent",
            lambda: self._structured(
                AnalysisPlan,
                PLANNER_PROMPT,
                f"SCHEMA\n{state['schema_context']}\n\nBUSINESS QUESTION\n{question}",
            ),
        )

        if not state["plan"].answerable:
            raise QuestionNotAnswerableError(
                state["plan"].unanswerable_reason,
                state["plan"].suggested_questions,
            )

        last_error = ""
        while state["attempts"] < self.max_attempts:
            state["attempts"] += 1
            repair_context = (
                f"\n\nPREVIOUS ATTEMPT FAILED\n{last_error}\n"
                "Correct the query rather than repeating it."
                if last_error
                else ""
            )
            proposal = self._trace(
                traces,
                "SQL repair agent" if last_error else "SQL agent",
                lambda repair_context=repair_context: self._structured(
                    SQLProposal,
                    SQL_PROMPT,
                    "SCHEMA\n"
                    f"{state['schema_context']}\n\nPLAN\n"
                    f"{state['plan'].model_dump_json(indent=2)}"
                    f"{repair_context}",
                ),
            )
            state["sql"] = proposal.sql
            state["sql_rationale"] = proposal.rationale
            started = time.perf_counter()
            try:
                validated_sql, result = self.workspace.execute(proposal.sql)
                state["sql"] = validated_sql
                state["columns"] = [str(column) for column in result.columns]
                state["rows"] = json.loads(result.to_json(orient="records", date_format="iso"))
                state["error"] = None
                traces.append(
                    TraceEvent(
                        stage="Guardrail + DuckDB executor",
                        status="success",
                        duration_ms=int((time.perf_counter() - started) * 1000),
                        detail=f"Read-only query returned {len(result)} row(s)",
                    )
                )
                break
            except Exception as exc:
                last_error = str(exc)[:500]
                state["error"] = last_error
                traces.append(
                    TraceEvent(
                        stage="Guardrail + DuckDB executor",
                        status="error",
                        duration_ms=int((time.perf_counter() - started) * 1000),
                        detail=last_error,
                    )
                )

        if state.get("error"):
            raise RuntimeError(
                f"The query agent could not produce a safe executable query after "
                f"{self.max_attempts} attempts: {state['error']}"
            )

        result_preview = json.dumps(state["rows"][:100], default=str)
        state["narrative"] = self._trace(
            traces,
            "Reviewer agent",
            lambda: self._structured(
                AnalysisNarrative,
                REVIEWER_PROMPT,
                f"QUESTION\n{question}\n\nPLAN\n{state['plan'].model_dump_json()}\n\n"
                f"EXECUTED SQL\n{state['sql']}\n\nRESULT COLUMNS\n{state['columns']}\n\n"
                f"RESULT ROWS\n{result_preview}",
            ),
        )

        state["narrative"].chart = self._trace(
            traces,
            "Visualization validator",
            lambda: select_chart(state["narrative"].chart, result, question),
        )

        return AnalysisResult(
            question=question,
            plan=state["plan"],
            sql=state["sql"],
            columns=state["columns"],
            rows=state["rows"],
            narrative=state["narrative"],
            traces=traces,
            attempts=state["attempts"],
        )
