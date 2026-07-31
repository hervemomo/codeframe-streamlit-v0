"""Survey loading, cleaning, language detection, and translation page."""

from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

from codeframe.exports import save_preprocessed_csv
from codeframe.loaders import load_survey_data
from codeframe.preprocessing import preprocess_data
from codeframe.translation import (
    make_batch_translator,
    translate_source_records,
)
from codeframe.workflow_state import set_preprocessed_data, survey_fingerprint
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

configure_page("Preprocessing")
initialize_session()
config = project_config_or_stop()

st.caption(
    "Load responses, remove invalid and duplicate records, detect language, and normalize "
    f"coding text to `{config.language.text_column}`."
)
uploaded = st.file_uploader("Survey file", type=["csv", "xls", "xlsx"])

preview: pd.DataFrame | None = None
sheet: str | int = 0
if uploaded is not None:
    try:
        suffix = Path(uploaded.name).suffix.lower()
        content = uploaded.getvalue()
        if suffix in {".xls", ".xlsx"}:
            workbook = pd.ExcelFile(BytesIO(content))
            sheet = st.selectbox("Worksheet", workbook.sheet_names)
            preview = pd.read_excel(BytesIO(content), sheet_name=sheet, nrows=25)
        else:
            preview = pd.read_csv(BytesIO(content), nrows=25)
    except Exception as error:
        show_failure(error)

if preview is not None and len(preview.columns):
    columns = [str(column) for column in preview.columns]
    response_column = st.selectbox("Response text column", columns)
    id_choice = st.selectbox("Response ID column", ["Create stable IDs", *columns])
    id_column = None if id_choice == "Create stable IDs" else id_choice
    first, second = st.columns(2)
    minimum_words = first.number_input(
        "Minimum words",
        min_value=1,
        max_value=50,
        value=3,
    )
    translate = second.checkbox(
        f"Translate non-{config.language.target_language_code} responses",
        value=True,
    )
    include_delay = st.checkbox("Use notebook API pacing delay", value=True)
    source_hash = survey_fingerprint(uploaded.name, uploaded.getvalue())
    existing_hash = st.session_state.get("survey_source_fingerprint")
    if (
        existing_hash is not None
        and existing_hash != source_hash
        and st.session_state.get("current_dataframe") is not None
    ):
        st.warning(
            "Running this new survey will discard active coding and refinement results. "
            "Existing output files remain available."
        )

    if st.button("Run preprocessing", type="primary"):
        try:
            source = persist_upload(uploaded, "inputs")
            output_dir = output_directory("preprocessing")
            loaded = load_survey_data(
                source,
                response_column,
                sheet_name=sheet,
                id_column=id_column,
            )
            processed = preprocess_data(
                loaded,
                output_dir=output_dir,
                min_words=int(minimum_words),
                language_config=config.language,
            )
            if translate:
                _, complete = api_services(config)
                processed = translate_source_records(
                    processed,
                    make_batch_translator(complete, model_config=config.models),
                    language_config=config.language,
                    delay=0.3 if include_delay else 0.0,
                )
            else:
                processed[config.language.text_column] = processed["cleaned_text"]
                processed["translation_status"] = "not_requested"
            processed_path = save_preprocessed_csv(
                processed,
                output_dir=output_dir,
                file_stem=uploaded_file_stem(uploaded),
            )
            audit_path = output_dir / "removed_records.xlsx"
            outputs = {
                "processed": processed_path,
                "removed_records": audit_path if audit_path.is_file() else None,
            }
            invalidated = set_preprocessed_data(
                st.session_state,
                processed,
                source_fingerprint=source_hash,
                outputs=outputs,
            )
            st.session_state.survey_file_stem = uploaded_file_stem(uploaded)
            st.session_state.preprocessing_source_path = source
            if invalidated:
                st.success("Preprocessing complete; stale coding and refinement state cleared.")
            else:
                st.success("Preprocessing complete.")
        except Exception as error:
            show_failure(error)

processed_result = st.session_state.get("preprocessed_df")
if isinstance(processed_result, pd.DataFrame):
    st.subheader("Preprocessing result")
    metrics = st.columns(3)
    metrics[0].metric("Responses retained", len(processed_result))
    language_counts = processed_result["detected_lang"].value_counts().to_dict()
    metrics[1].metric("Detected languages", len(language_counts))
    translated_count = int(
        processed_result.get("translation_status", pd.Series(dtype=str))
        .astype(str)
        .str.startswith("translated")
        .sum()
    )
    metrics[2].metric("Responses translated", translated_count)
    st.dataframe(
        processed_result[
            [
                column
                for column in [
                    "response_id",
                    "original_text",
                    "detected_lang",
                    "detected_lang_status",
                    "translation_status",
                    config.language.text_column,
                ]
                if column in processed_result.columns
            ]
        ].head(20),
        use_container_width=True,
        hide_index=True,
    )
