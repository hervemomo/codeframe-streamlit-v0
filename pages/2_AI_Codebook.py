"""AI-generated codebook and automated coding page."""

import time

import streamlit as st

from ui.common import (
    api_services,
    configure_page,
    initialize_session,
    output_directory,
    project_config_or_stop,
    require_preprocessed,
    show_failure,
)

configure_page("AI Codebook")
initialize_session()
config = project_config_or_stop()

if config.coding.mode != "ai":
    st.info(
        "This project uses the user-supplied codebook path. Open **User Codebook**, "
        "or change the path in **Project Setup**."
    )
    st.stop()

dataframe = require_preprocessed()

import pandas as pd  # noqa: E402

from codeframe.ai_coding import run_ai_codebook_workflow  # noqa: E402
from codeframe.reporting import calculate_frequencies  # noqa: E402
from codeframe.workflow_state import set_coding_result  # noqa: E402

st.caption(
    "The explicit action below generates embeddings, discovers themes, builds a codebook, "
    "codes responses, and writes the report bundle. Ordinary reruns do not repeat it."
)

include_charts = st.checkbox("Generate report charts", value=True)
include_excel = st.checkbox("Generate Excel report", value=True)
use_delay = st.checkbox("Use notebook API pacing delay", value=True)

if st.button("Generate codebook and code responses", type="primary"):
    try:
        client, complete = api_services(config)
        with st.spinner("Running the AI codebook workflow…"):
            result = run_ai_codebook_workflow(
                dataframe,
                client,
                complete,
                output_dir=output_directory("ai_codebook"),
                file_stem=st.session_state.get("survey_file_stem", "survey"),
                survey_context=config.survey_context,
                text_column=config.language.text_column,
                language_config=config.language,
                model_config=config.models,
                coding_config=config.coding,
                clustering_config=config.clustering,
                include_charts=include_charts,
                include_excel=include_excel,
                usage_tracker=st.session_state.usage_tracker,
                sleep=time.sleep if use_delay else lambda _: None,
            )
        set_coding_result(
            st.session_state,
            path="ai",
            result=result,
            dataframe=result.dataframe,
            codebook=result.codebook,
            outputs=result.outputs,
        )
        st.success("AI codebook generation and response coding complete.")
    except Exception as error:
        show_failure(error)

result = st.session_state.get("coding_result")
if st.session_state.get("active_path") == "ai" and result is not None:
    coded = st.session_state.get("current_dataframe")
    codebook = st.session_state.get("current_codebook")
    if isinstance(coded, pd.DataFrame) and isinstance(codebook, dict):
        st.subheader("Coding result")
        metrics = st.columns(3)
        metrics[0].metric("Responses", len(coded))
        metrics[1].metric("Codes", len(codebook.get("codes", [])))
        coded_count = int((coded.get("num_codes", pd.Series(dtype=int)) > 0).sum())
        metrics[2].metric("Coded responses", coded_count)
        st.dataframe(
            calculate_frequencies(coded, codebook),
            use_container_width=True,
            hide_index=True,
        )
