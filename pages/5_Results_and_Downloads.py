"""Final summaries, usage accounting, and artifact downloads."""

import json
from pathlib import Path

import streamlit as st

from ui.common import (
    configure_page,
    download_path,
    initialize_session,
    output_directory,
    project_config_or_stop,
)

configure_page("Results & Downloads")
initialize_session()
project_config_or_stop()

dataframe = st.session_state.get("current_dataframe")
codebook = st.session_state.get("current_codebook")
if dataframe is None or not isinstance(codebook, dict):
    st.info("Complete either coding path before viewing results.")
    st.stop()

import pandas as pd  # noqa: E402

from codeframe.reporting import (  # noqa: E402
    calculate_frequencies,
    generate_cooccurrence_matrix,
)
from codeframe.workflow_state import (  # noqa: E402
    elapsed_seconds,
    record_output_paths,
    usage_summary,
)

if not isinstance(dataframe, pd.DataFrame):
    st.info("Complete either coding path before viewing results.")
    st.stop()

code_count = len(codebook.get("codes", []))
num_codes = dataframe.get("num_codes", pd.Series(0, index=dataframe.index))
coded_count = int((num_codes > 0).sum())
multi_label_count = int((num_codes > 1).sum())
tracker = st.session_state.usage_tracker
totals = tracker.totals
output_paths = tuple(st.session_state.get("output_paths", ()))

st.subheader("Run summary")
metrics = st.columns(6)
metrics[0].metric("Responses", len(dataframe))
metrics[1].metric("Codes", code_count)
metrics[2].metric("Coded", coded_count)
metrics[3].metric("Multi-label", multi_label_count)
metrics[4].metric("API calls", len(tracker.records))
metrics[5].metric("Total tokens", totals.total_tokens)
st.caption(
    f"Active path: {st.session_state.get('active_path', 'unknown')} · "
    f"Elapsed session time: {elapsed_seconds(st.session_state):.1f} seconds · "
    f"Saved files: {len(output_paths)}"
)

frequency_tab, cooccurrence_tab, usage_tab = st.tabs(
    ["Frequencies", "Co-occurrence", "Model usage"]
)
with frequency_tab:
    st.dataframe(
        calculate_frequencies(dataframe, codebook),
        use_container_width=True,
        hide_index=True,
    )
with cooccurrence_tab:
    matrix = generate_cooccurrence_matrix(dataframe, codebook)
    if matrix.empty:
        st.info("No assignment columns are available for co-occurrence.")
    else:
        st.dataframe(matrix.iloc[:30, :30], use_container_width=True)
        if len(matrix) > 30:
            st.caption("Preview limited to the first 30 codes; the workbook contains all codes.")
with usage_tab:
    usage = tracker.to_dataframe()
    summary = usage_summary(usage)
    if summary.empty:
        st.info("No model requests have been recorded in this session.")
    else:
        st.dataframe(summary, use_container_width=True, hide_index=True)
    if st.button("Save usage log"):
        destination = (
            output_directory("results")
            / f"{st.session_state.get('survey_file_stem', 'survey')}_llm_usage_log.csv"
        )
        usage.to_csv(destination, index=False)
        record_output_paths(st.session_state, destination)
        st.success(f"Saved {destination.name}.")

st.subheader("Direct exports")
csv_bytes = dataframe.to_csv(index=False).encode("utf-8")
st.download_button(
    "Download current coded data (CSV)",
    data=csv_bytes,
    file_name=f"{st.session_state.get('survey_file_stem', 'survey')}_coded_current.csv",
    mime="text/csv",
)
codebook_bytes = json.dumps(codebook, ensure_ascii=False, indent=2).encode("utf-8")
st.download_button(
    "Download current codebook (JSON)",
    data=codebook_bytes,
    file_name=f"{st.session_state.get('survey_file_stem', 'survey')}_codebook_current.json",
    mime="application/json",
)

st.subheader("Saved workflow files")
record_output_paths(st.session_state, output_paths)
available = [path for path in st.session_state.get("output_paths", ()) if isinstance(path, Path)]
if not available:
    st.info("No saved report files are available.")
else:
    for path in available:
        download_path(path)
