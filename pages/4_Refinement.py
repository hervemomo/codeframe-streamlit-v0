"""Confirmed split and merge refinements over the active coding result."""

import time
from typing import Any

import streamlit as st

from ui.common import (
    api_services,
    configure_page,
    initialize_session,
    output_directory,
    project_config_or_stop,
    show_failure,
    split_lines,
)


def no_completion(**_: Any) -> str:
    """A completion boundary that is unreachable for unconfirmed operations."""

    return ""


configure_page("Refinement")
initialize_session()
config = project_config_or_stop()

dataframe = st.session_state.get("current_dataframe")
codebook = st.session_state.get("current_codebook")
if dataframe is None or not isinstance(codebook, dict):
    st.info("Complete either coding path before refining codes.")
    st.stop()

import pandas as pd  # noqa: E402

from codeframe.codebook import clean_code_id, codebook_has_code_ids  # noqa: E402
from codeframe.merge_codes import apply_confirmed_merges  # noqa: E402
from codeframe.reporting import calculate_frequencies  # noqa: E402
from codeframe.split_codes import apply_confirmed_splits  # noqa: E402
from codeframe.workflow_state import (  # noqa: E402
    begin_refinement_attempt,
    set_refinement_result,
)

if not isinstance(dataframe, pd.DataFrame):
    st.info("Complete either coding path before refining codes.")
    st.stop()

st.caption(
    "Split and merge operate on the current result. Confirmed operations are chained, "
    "so either operation can follow the other repeatedly."
)
history = st.session_state.get("refinement_history", ())
if history:
    st.write("Refinement history: " + " → ".join(str(item).title() for item in history))

code_names = [str(code["name"]) for code in codebook.get("codes", [])]
split_tab, merge_tab = st.tabs(["Split a code", "Merge codes"])

with split_tab:
    parent = st.selectbox("Parent code", code_names, key="split-parent")
    proposed_count = st.number_input(
        "AI-proposed subcodes when names are blank",
        min_value=2,
        max_value=10,
        value=3,
    )
    subcode_names = split_lines(
        st.text_area(
            "Subcode names (one per line; leave blank for AI proposals)",
            key="split-names",
        )
    )
    subcode_ids = split_lines(
        st.text_area(
            "Subcode IDs (one per line; optional)",
            key="split-ids",
            disabled=not codebook_has_code_ids(codebook),
        )
    )
    subcode_definitions = split_lines(
        st.text_area(
            "Subcode definitions (one per line; optional)",
            key="split-definitions",
        )
    )
    split_options = st.columns(3)
    enrich_subcodes = split_options[0].checkbox(
        "Enrich subcode metadata",
        value=True,
        key="split-enrich",
    )
    preserve_parent = split_options[1].checkbox(
        "Preserve parent code",
        value=False,
        key="split-preserve",
    )
    use_split_delay = split_options[2].checkbox(
        "Use API pacing delay",
        value=True,
        key="split-delay",
    )
    confirm_split = st.checkbox(
        f'I confirm splitting "{parent}" and recoding its assigned responses.',
        key="split-confirm",
    )
    if st.button("Apply split", type="primary"):
        begin_refinement_attempt(st.session_state, "split")
        split_config: dict[str, Any] = {
            "parent_code": parent,
            "subcodes": subcode_names,
            "subcode_ids": subcode_ids,
            "subcode_definitions": subcode_definitions,
            "n_subcodes_proposed": int(proposed_count),
            "enrich": enrich_subcodes,
            "preserve_parent": preserve_parent,
        }
        try:
            if confirm_split:
                _, complete = api_services(config)
            else:
                complete = no_completion
            with st.spinner("Applying confirmed split…"):
                result = apply_confirmed_splits(
                    dataframe,
                    codebook,
                    complete,
                    [split_config],
                    confirmed=confirm_split,
                    survey_context=config.survey_context,
                    text_column=config.language.text_column,
                    output_dir=output_directory("refinement"),
                    output_file="split.xlsx",
                    model_config=config.models,
                    coding_config=config.coding,
                    include_charts=True,
                    sleep=time.sleep if use_split_delay else lambda _: None,
                )
            if result.did_run:
                set_refinement_result(
                    st.session_state,
                    kind="split",
                    result=result,
                    dataframe=result.dataframe,
                    codebook=result.codebook,
                    outputs=result.outputs,
                )
                st.success("Split applied. Its result is now the active refinement input.")
            else:
                st.info("No split was run because confirmation was not selected.")
        except Exception as error:
            show_failure(error)

with merge_tab:
    sources = st.multiselect(
        "Codes to merge",
        code_names,
        key="merge-sources",
    )
    merged_name = st.text_input(
        "Merged code name (blank lets AI propose it)",
        key="merge-name",
    )
    merged_id = st.text_input(
        "Merged code ID (optional)",
        key="merge-id",
        disabled=not codebook_has_code_ids(codebook),
    )
    merged_definition = st.text_area(
        "Merged definition (optional)",
        key="merge-definition",
    )
    merge_columns = st.columns(3)
    inclusion = split_lines(merge_columns[0].text_area("Inclusion criteria", key="merge-inclusion"))
    exclusion = split_lines(merge_columns[1].text_area("Exclusion criteria", key="merge-exclusion"))
    examples = split_lines(merge_columns[2].text_area("Example verbatims", key="merge-examples"))
    enrich_merged = st.checkbox("Enrich merged metadata with AI", value=True)
    confirm_merge = st.checkbox(
        "I confirm this OR-based merge and replacement of the source codes.",
        key="merge-confirm",
    )
    if st.button("Apply merge", type="primary"):
        begin_refinement_attempt(st.session_state, "merge")
        merge_config: dict[str, Any] = {
            "codes_to_merge": sources,
            "merged_name": merged_name,
            "merged_code_id": clean_code_id(merged_id),
            "merged_definition": merged_definition,
            "merged_inclusion_criteria": inclusion,
            "merged_exclusion_criteria": exclusion,
            "merged_example_verbatims": examples,
            "enrich": enrich_merged,
        }
        try:
            if confirm_merge:
                _, complete = api_services(config)
            else:
                complete = no_completion
            with st.spinner("Applying confirmed merge…"):
                result = apply_confirmed_merges(
                    dataframe,
                    codebook,
                    complete,
                    [merge_config],
                    confirmed=confirm_merge,
                    survey_context=config.survey_context,
                    text_column=config.language.text_column,
                    output_dir=output_directory("refinement"),
                    output_file="merge.xlsx",
                    model_config=config.models,
                    include_charts=True,
                )
            if result.did_run:
                set_refinement_result(
                    st.session_state,
                    kind="merge",
                    result=result,
                    dataframe=result.dataframe,
                    codebook=result.codebook,
                    outputs=result.outputs,
                )
                st.success("Merge applied. Its result is now the active refinement input.")
            else:
                st.info("No merge was run because confirmation was not selected.")
        except Exception as error:
            show_failure(error)

active_dataframe = st.session_state.get("current_dataframe")
active_codebook = st.session_state.get("current_codebook")
if isinstance(active_dataframe, pd.DataFrame) and isinstance(active_codebook, dict):
    st.subheader("Current code frequencies")
    st.dataframe(
        calculate_frequencies(active_dataframe, active_codebook),
        use_container_width=True,
        hide_index=True,
    )
