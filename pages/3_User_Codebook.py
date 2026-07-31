"""User-supplied codebook preparation and coding page."""

import time
from dataclasses import replace
from io import BytesIO
from pathlib import Path

import streamlit as st

from ui.common import (
    api_services,
    configure_page,
    initialize_session,
    output_directory,
    persist_upload,
    project_config_or_stop,
    show_failure,
    uploaded_file_stem,
)

configure_page("User Codebook")
initialize_session()
config = project_config_or_stop()

if config.coding.mode != "manual":
    st.info(
        "This project uses the AI-generated codebook path. Open **AI Codebook**, "
        "or change the path in **Project Setup**."
    )
    st.stop()

import pandas as pd  # noqa: E402

from codeframe.reporting import calculate_frequencies  # noqa: E402
from codeframe.user_codebook import (  # noqa: E402
    prepare_user_codebook,
    run_user_codebook_coding,
)
from codeframe.workflow_state import (  # noqa: E402
    set_coding_result,
    set_prepared_user_codebook,
)

st.subheader("Part 1 · Prepare the codebook")
st.caption(
    "Part 1 is independent of survey preprocessing. Review the generated JSON or Excel "
    "artifact before running Part 2."
)
uploaded = st.file_uploader("Codebook file", type=["csv", "xls", "xlsx"])

preview: pd.DataFrame | None = None
sheet: str | int = 0
if uploaded is not None:
    try:
        content = uploaded.getvalue()
        suffix = Path(uploaded.name).suffix.lower()
        if suffix in {".xls", ".xlsx"}:
            workbook = pd.ExcelFile(BytesIO(content))
            sheet = st.selectbox("Codebook worksheet", workbook.sheet_names)
            preview = pd.read_excel(BytesIO(content), sheet_name=sheet, nrows=25)
        else:
            preview = pd.read_csv(BytesIO(content), nrows=25)
    except Exception as error:
        show_failure(error)

if preview is not None and len(preview.columns):
    columns = [str(column) for column in preview.columns]
    name_column = st.selectbox("Code name column", columns)

    def optional_column(label: str) -> str | None:
        selected = st.selectbox(label, ["Auto-detect / absent", *columns])
        return None if selected == "Auto-detect / absent" else selected

    mapping_columns = st.columns(3)
    with mapping_columns[0]:
        id_column = optional_column("Code ID column")
        definition_column = optional_column("Definition column")
    with mapping_columns[1]:
        inclusion_column = optional_column("Inclusion criteria column")
        exclusion_column = optional_column("Exclusion criteria column")
    with mapping_columns[2]:
        examples_column = optional_column("Example verbatims column")
        catch_all_id = st.text_input("Catch-all code ID", value="")
    enhance = st.checkbox("Enhance missing codebook metadata with AI", value=True)
    if st.session_state.get("current_dataframe") is not None:
        st.warning(
            "Preparing a new codebook will discard active coding and refinement state. "
            "Existing output files remain available."
        )

    if st.button("Prepare user codebook", type="primary"):
        try:
            source = persist_upload(uploaded, "inputs")
            settings = replace(config.user_codebook, enhance_with_ai=enhance)
            complete = api_services(config)[1] if enhance else None
            with st.spinner("Preparing the user codebook…"):
                prepared = prepare_user_codebook(
                    source,
                    complete,
                    output_dir=output_directory("user_codebook"),
                    file_stem=uploaded_file_stem(uploaded),
                    catch_all_code_id=catch_all_id,
                    language_config=config.language,
                    model_config=config.models,
                    config=settings,
                    name_column=name_column,
                    id_column=id_column,
                    definition_column=definition_column,
                    inclusion_column=inclusion_column,
                    exclusion_column=exclusion_column,
                    examples_column=examples_column,
                    sheet_name=sheet,
                )
            invalidated = set_prepared_user_codebook(
                st.session_state,
                prepared,
                outputs=[prepared.json_path, prepared.excel_path],
            )
            st.session_state.user_codebook_settings = settings
            if invalidated:
                st.success(
                    "Codebook prepared and stale coding/refinement state cleared. "
                    "Review the saved artifacts before Part 2."
                )
            else:
                st.success("Codebook prepared. Review the saved artifacts before Part 2.")
        except Exception as error:
            show_failure(error)

prepared = st.session_state.get("prepared_user_codebook")
if prepared is not None:
    codebook = prepared.codebook
    st.dataframe(
        pd.DataFrame(codebook["codes"])[
            [
                column
                for column in ["code_id", "name", "definition", "source"]
                if column in pd.DataFrame(codebook["codes"]).columns
            ]
        ].head(50),
        use_container_width=True,
        hide_index=True,
    )
    st.download_button(
        "Download prepared codebook JSON",
        data=prepared.json_path.read_bytes(),
        file_name=prepared.json_path.name,
        mime="application/json",
    )

st.divider()
st.subheader("Part 2 · Code survey responses")
processed = st.session_state.get("preprocessed_df")
if processed is None:
    st.info("Run **Preprocessing** before Part 2. Part 1 remains available above.")
elif prepared is None:
    st.info("Prepare and review the user codebook before Part 2.")
else:
    include_charts = st.checkbox("Generate report charts", value=True, key="manual-charts")
    use_delay = st.checkbox("Use notebook API pacing delay", value=True, key="manual-delay")
    if st.button("Code responses with prepared codebook", type="primary"):
        try:
            _, complete = api_services(config)
            with st.spinner("Coding responses with the prepared codebook…"):
                result = run_user_codebook_coding(
                    processed,
                    prepared.codebook,
                    complete,
                    output_dir=output_directory("user_coding"),
                    file_stem=st.session_state.get("survey_file_stem", "survey"),
                    survey_context=config.survey_context,
                    question=config.survey_question,
                    text_column=config.language.text_column,
                    model_config=config.models,
                    config=st.session_state.get("user_codebook_settings", config.user_codebook),
                    include_charts=include_charts,
                    sleep=time.sleep if use_delay else lambda _: None,
                )
            set_coding_result(
                st.session_state,
                path="manual",
                result=result,
                dataframe=result.dataframe,
                codebook=result.codebook,
                outputs=result.outputs,
            )
            st.success("User-codebook response coding complete.")
        except Exception as error:
            show_failure(error)

if st.session_state.get("active_path") == "manual":
    coded = st.session_state.get("current_dataframe")
    active_codebook = st.session_state.get("current_codebook")
    if isinstance(coded, pd.DataFrame) and isinstance(active_codebook, dict):
        st.subheader("Coding result")
        st.dataframe(
            calculate_frequencies(coded, active_codebook),
            use_container_width=True,
            hide_index=True,
        )
