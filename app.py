from __future__ import annotations

import io
import logging

import pandas as pd
import streamlit as st
from openai import AuthenticationError, RateLimitError

from datapilot import (
    AgenticAnalyst,
    AnalysisError,
    DataWorkspace,
    QuestionNotAnswerableError,
    StructuredOutputError,
)

LOGGER = logging.getLogger(__name__)

st.set_page_config(
    page_title="DataPilot",
    page_icon=":material/query_stats:",
    layout="centered",
)


def clear_analysis() -> None:
    st.session_state.pop("analysis_result", None)
    st.session_state.pop("analysis_error", None)


def change_files() -> None:
    clear_analysis()
    st.session_state["analysis_question"] = ""


def apply_example(example_key: str) -> None:
    selected = st.session_state.get(example_key)
    if selected:
        st.session_state["analysis_question"] = selected
        clear_analysis()


@st.cache_data(max_entries=10, show_spinner=False)
def read_uploaded_table(name: str, content: bytes) -> pd.DataFrame:
    if name.lower().endswith(".csv"):
        return pd.read_csv(io.BytesIO(content))
    return pd.read_parquet(io.BytesIO(content))


def load_workspace(uploaded_files: list) -> DataWorkspace | None:
    if not uploaded_files:
        return None

    tables: dict[str, pd.DataFrame] = {}
    for file in uploaded_files:
        stem = file.name.rsplit(".", 1)[0]
        tables[stem] = read_uploaded_table(file.name, file.getvalue())
    return DataWorkspace(tables)


def uploaded_examples(workspace: DataWorkspace) -> list[str]:
    examples: list[str] = []
    for frame in workspace.tables.values():
        numeric = [
            str(column)
            for column in frame.columns
            if pd.api.types.is_numeric_dtype(frame[column])
        ]
        categorical = [
            str(column)
            for column in frame.columns
            if not pd.api.types.is_numeric_dtype(frame[column])
            and frame[column].nunique(dropna=True) <= 30
        ]
        if numeric and categorical:
            examples.append(f"Compare the average {numeric[0]} by {categorical[0]}.")
        if len(numeric) >= 2:
            examples.append(f"How strongly are {numeric[0]} and {numeric[1]} related?")
        if numeric:
            examples.append(f"Show the distribution of {numeric[0]} and highlight unusual values.")
        if examples:
            break
    return examples[:3] or ["How many rows are in this dataset?"]


def render_error(error: dict) -> None:
    kind = error["kind"]
    if kind == "question":
        st.warning(error["message"], icon=":material/dataset:")
        suggestions = error.get("suggestions", [])
        if suggestions:
            st.caption("Try a question that matches the uploaded columns:")
            for suggestion in suggestions:
                st.markdown(f"- {suggestion}")
    elif kind == "rate_limit":
        st.warning(
            "Groq's free-tier limit is temporarily busy. Wait a minute and run the question again.",
            icon=":material/hourglass_top:",
        )
    elif kind == "authentication":
        st.error(
            "The API key was not accepted. Run `scripts\\save_groq_key.ps1` again and restart the app.",
            icon=":material/key:",
        )
    elif kind == "format":
        st.warning(
            "The model could not format this analysis correctly after a retry. "
            "Try a shorter, more specific question.",
            icon=":material/refresh:",
        )
    else:
        st.error(
            "The analysis could not be completed. Check the dataset and try a simpler question.",
            icon=":material/error:",
        )


def run_analysis(workspace: DataWorkspace, question: str) -> None:
    clear_analysis()
    status = st.status("Running agentic analysis", expanded=True)
    try:
        with status:
            st.write("Planning the analysis against the available schema")
            result = AgenticAnalyst(workspace=workspace).analyze(question)
            st.write("Validated and executed read-only SQL")
            st.write("Reviewed the evidence and prepared the answer")
            status.update(label="Analysis complete", state="complete", expanded=False)
        st.session_state["analysis_result"] = result
    except QuestionNotAnswerableError as exc:
        status.update(label="Question does not match this dataset", state="error", expanded=False)
        st.session_state["analysis_error"] = {
            "kind": "question",
            "message": exc.reason,
            "suggestions": exc.suggestions,
        }
    except RateLimitError:
        status.update(label="Free-tier limit reached", state="error", expanded=False)
        st.session_state["analysis_error"] = {"kind": "rate_limit"}
    except AuthenticationError:
        status.update(label="API key was not accepted", state="error", expanded=False)
        st.session_state["analysis_error"] = {"kind": "authentication"}
    except StructuredOutputError:
        status.update(label="Model response needs another try", state="error", expanded=False)
        st.session_state["analysis_error"] = {"kind": "format"}
    except AnalysisError:
        status.update(label="Analysis stopped", state="error", expanded=False)
        st.session_state["analysis_error"] = {"kind": "analysis"}
    except Exception:
        status.update(label="Analysis stopped", state="error", expanded=False)
        LOGGER.exception("Unexpected analysis failure")
        st.session_state["analysis_error"] = {"kind": "unexpected"}


st.session_state.setdefault("analysis_question", "")

st.title("DataPilot")
st.caption(
    "Ask questions in plain English. DataPilot plans the analysis, validates read-only SQL, "
    "and shows the evidence behind every answer."
)
with st.container(horizontal=True):
    st.badge("Schema aware", icon=":material/schema:", color="blue")
    st.badge("Read-only SQL", icon=":material/verified_user:", color="green")
    st.badge("Inspectable", icon=":material/visibility:", color="gray")

with st.sidebar:
    st.header("Upload data")
    uploaded = st.file_uploader(
        "CSV or Parquet files",
        type=["csv", "parquet", "pq"],
        accept_multiple_files=True,
        key="uploaded_files",
        on_change=change_files,
    )
    st.caption("Only the schema and three sample rows are sent to Groq. SQL runs locally.")

    st.caption(
        ":material/security: SELECT-only queries · known tables only · "
        "500-row result cap · no external file access"
    )

try:
    workspace = load_workspace(uploaded)
except Exception:
    LOGGER.exception("Failed to load uploaded data")
    st.error(
        "The uploaded file could not be read. Confirm that it is a valid CSV or Parquet file.",
        icon=":material/broken_image:",
    )
    st.stop()

if workspace is None:
    with st.container(border=True):
        st.subheader(":material/upload_file: Upload data to begin")
        st.write("Choose one or more CSV or Parquet files from the sidebar.")
    st.stop()

total_rows = sum(len(frame) for frame in workspace.tables.values())
total_columns = sum(len(frame.columns) for frame in workspace.tables.values())
with st.container(horizontal=True):
    st.metric("Tables", len(workspace.tables), border=True)
    st.metric("Rows", f"{total_rows:,}", border=True)
    st.metric("Columns", total_columns, border=True)

with st.expander("Preview loaded data", icon=":material/table_view:"):
    table_tabs = st.tabs(list(workspace.tables))
    for tab, (name, frame) in zip(table_tabs, workspace.tables.items(), strict=True):
        with tab:
            st.caption(f"{len(frame):,} rows × {len(frame.columns)} columns")
            st.dataframe(frame.head(100), hide_index=True, key=f"preview_{name}")

examples = uploaded_examples(workspace)
example_key = "upload_example"

with st.container(border=True):
    st.subheader(":material/chat: Ask your data")
    st.caption("Choose an example or write a question using the fields in the loaded dataset.")
    st.pills(
        "Example questions",
        examples,
        key=example_key,
        on_change=apply_example,
        args=(example_key,),
        label_visibility="collapsed",
    )

    with st.form("analysis_form", border=False):
        question = st.text_area(
            "Business question",
            key="analysis_question",
            placeholder="Example: Compare average price by location.",
            height=100,
        )
        submitted = st.form_submit_button(
            "Run analysis",
            type="primary",
            icon=":material/play_arrow:",
            width="stretch",
        )

if submitted:
    if len(question.strip()) < 5:
        st.session_state["analysis_error"] = {
            "kind": "question",
            "message": "Enter a specific question about the loaded dataset.",
            "suggestions": examples,
        }
    else:
        run_analysis(workspace, question)

error = st.session_state.get("analysis_error")
if error:
    render_error(error)

result = st.session_state.get("analysis_result")
if result:
    st.space("medium")
    st.subheader(result.narrative.headline)
    st.write(result.narrative.summary)

    with st.container(horizontal=True):
        st.metric("Rows returned", len(result.rows), border=True)
        st.metric("SQL attempts", result.attempts, border=True)
        st.metric(
            "Workflow latency",
            f"{sum(event.duration_ms for event in result.traces) / 1000:.1f}s",
            border=True,
        )

    result_frame = pd.DataFrame(result.rows, columns=result.columns)
    overview_tab, data_tab, sql_tab, trace_tab = st.tabs(
        [
            ":material/insights: Overview",
            ":material/table: Data",
            ":material/code: SQL & plan",
            ":material/account_tree: Trace",
        ]
    )

    with overview_tab:
        chart = result.narrative.chart
        if chart.chart_type != "none" and not result_frame.empty:
            with st.container(border=True):
                st.subheader(f":material/auto_graph: {chart.title}")
                st.caption(
                    f"Automatically generated {chart.chart_type} chart from the query result."
                )
                if chart.chart_type == "bar":
                    st.bar_chart(result_frame, x=chart.x, y=chart.y)
                elif chart.chart_type == "line":
                    st.line_chart(result_frame, x=chart.x, y=chart.y)
                else:
                    st.scatter_chart(result_frame, x=chart.x, y=chart.y)

        with st.container(border=True):
            st.markdown("**Key findings**")
            for finding in result.narrative.key_findings:
                st.markdown(f"- {finding}")
            if result.narrative.caveats:
                st.markdown("**Caveats**")
                for caveat in result.narrative.caveats:
                    st.markdown(f"- {caveat}")

    with data_tab:
        st.dataframe(result_frame, hide_index=True, key="analysis_data")

    with sql_tab:
        st.markdown("**Analysis plan**")
        for step in result.plan.approach:
            st.markdown(f"- {step}")
        if result.plan.assumptions:
            st.markdown("**Assumptions**")
            for assumption in result.plan.assumptions:
                st.markdown(f"- {assumption}")
        st.markdown("**Executed SQL**")
        st.code(result.sql, language="sql")

    with trace_tab:
        trace_frame = pd.DataFrame([event.model_dump() for event in result.traces])
        st.dataframe(trace_frame, hide_index=True, key="analysis_trace")
