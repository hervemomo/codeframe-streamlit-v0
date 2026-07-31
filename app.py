"""Project Setup page for the Codeframe Streamlit application."""

import streamlit as st

from codeframe.config import CodingConfig, LanguageConfig, ModelConfig, ProjectConfig
from codeframe.workflow_state import (
    has_downstream_results,
    project_fingerprint,
    update_project_config,
)
from ui.common import configure_page, initialize_session

configure_page("Project Setup")
initialize_session()

st.caption(
    "Configure one project, preprocess the survey, choose either the AI-generated "
    "or user-supplied codebook path, refine if needed, then download results."
)

existing = st.session_state.get("project_config")
default_question = existing.survey_question if isinstance(existing, ProjectConfig) else ""
default_context = existing.survey_context if isinstance(existing, ProjectConfig) else ""
default_mode = existing.coding.mode if isinstance(existing, ProjectConfig) else "manual"
default_target = (
    existing.language.target_language_code if isinstance(existing, ProjectConfig) else "fr"
)
default_codebook_language = (
    existing.language.codebook_language_code if isinstance(existing, ProjectConfig) else "fr"
)

with st.form("project-setup"):
    question = st.text_area(
        "Survey question",
        value=default_question,
        placeholder="What did respondents say about their experience?",
    )
    context = st.text_area(
        "Survey context",
        value=default_context,
        placeholder="Audience, program, market, or other context used in model prompts.",
    )
    mode = st.radio(
        "Coding path",
        options=["manual", "ai"],
        index=0 if default_mode == "manual" else 1,
        format_func=lambda value: (
            "User-supplied codebook" if value == "manual" else "AI-generated codebook"
        ),
        horizontal=True,
    )
    first, second = st.columns(2)
    target_language = first.selectbox(
        "Response target language",
        options=["fr", "en"],
        index=0 if default_target == "fr" else 1,
    )
    codebook_language = second.selectbox(
        "Codebook language",
        options=["fr", "en"],
        index=0 if default_codebook_language == "fr" else 1,
    )
    with st.expander("Advanced model settings"):
        reasoning_model = st.text_input(
            "Reasoning model",
            value=existing.models.reasoning_model
            if isinstance(existing, ProjectConfig)
            else "gpt-5.4-mini",
        )
        coding_model = st.text_input(
            "Coding and translation model",
            value=existing.models.coding_model
            if isinstance(existing, ProjectConfig)
            else "gpt-4.1-mini",
        )
        embedding_model = st.text_input(
            "Embedding model",
            value=existing.models.embedding_model
            if isinstance(existing, ProjectConfig)
            else "text-embedding-3-small",
        )
        maximum_codes = st.number_input(
            "Maximum codes per response",
            min_value=1,
            max_value=20,
            value=existing.coding.maximum_codes_per_response
            if isinstance(existing, ProjectConfig)
            else 3,
        )
    save = st.form_submit_button("Save project setup", type="primary")

pending_config = None
try:
    pending_config = ProjectConfig(
        survey_question=question,
        survey_context=context,
        language=LanguageConfig(
            target_language_code=target_language,
            codebook_language_code=codebook_language,
        ),
        models=ModelConfig(
            reasoning_model=reasoning_model,
            coding_model=coding_model,
            embedding_model=embedding_model,
        ),
        coding=CodingConfig(
            mode=mode,
            maximum_codes_per_response=int(maximum_codes),
        ),
    )
except ValueError:
    if save:
        st.error("Survey question, context, and model names must not be blank.")

if (
    pending_config is not None
    and has_downstream_results(st.session_state)
    and st.session_state.get("project_fingerprint") != project_fingerprint(pending_config)
):
    st.warning(
        "Saving these changed settings will discard preprocessing, coding, and refinement "
        "results. Existing output files remain available for download."
    )

if save and pending_config is not None:
    invalidated = update_project_config(st.session_state, pending_config)
    if invalidated:
        st.success("Project updated and dependent workflow state cleared.")
    else:
        st.success("Project setup saved.")

active = st.session_state.get("project_config")
if isinstance(active, ProjectConfig):
    label = "User Codebook" if active.coding.mode == "manual" else "AI Codebook"
    st.subheader("Next step")
    st.write(
        f"Open **Preprocessing**, then continue to **{label}**. The other coding path is "
        "not required."
    )
