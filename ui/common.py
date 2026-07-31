"""Shared Streamlit presentation and integration helpers."""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

from codeframe.config import ProjectConfig
from codeframe.llm_client import TextCompletion, make_text_completion
from codeframe.usage import UsageTracker
from codeframe.workflow_state import initialize_workflow_state

logger = logging.getLogger(__name__)

APP_TITLE = "Codeframe"


def configure_page(title: str) -> None:
    """Configure one application page consistently."""

    st.set_page_config(page_title=f"{title} · {APP_TITLE}", page_icon="🧭", layout="wide")
    st.title(title)


def initialize_session() -> None:
    """Initialize rerun-safe session objects and the session output directory."""

    initialize_workflow_state(st.session_state)
    if "usage_tracker" not in st.session_state:
        st.session_state.usage_tracker = UsageTracker()
    if "session_output_dir" not in st.session_state:
        workspace_tmp = Path.cwd() / "tmp"
        workspace_tmp.mkdir(parents=True, exist_ok=True)
        st.session_state.session_output_dir = Path(
            tempfile.mkdtemp(prefix="codeframe-session-", dir=workspace_tmp)
        )


def project_config_or_stop() -> ProjectConfig:
    """Require project setup before a dependent page renders."""

    config = st.session_state.get("project_config")
    if not isinstance(config, ProjectConfig):
        st.info("Complete **Project Setup** first.")
        st.stop()
    return config


def require_preprocessed() -> Any:
    """Require preprocessing before a coding workflow renders."""

    dataframe = st.session_state.get("preprocessed_df")
    if dataframe is None:
        st.info("Run **Preprocessing** first.")
        st.stop()
    return dataframe


def output_directory(name: str) -> Path:
    """Return a named directory scoped to this application session."""

    destination = Path(st.session_state.session_output_dir) / name
    destination.mkdir(parents=True, exist_ok=True)
    return destination


def persist_upload(uploaded_file: Any, directory_name: str) -> Path:
    """Persist an uploaded file under a sanitized name in this session."""

    destination_dir = output_directory(directory_name)
    destination = destination_dir / Path(str(uploaded_file.name)).name
    destination.write_bytes(uploaded_file.getvalue())
    return destination


def uploaded_file_stem(uploaded_file: Any) -> str:
    """Return a safe report stem derived from an uploaded filename."""

    stem = Path(str(uploaded_file.name)).stem.strip()
    return stem or "survey"


def api_services(config: ProjectConfig) -> tuple[OpenAI, TextCompletion]:
    """Create OpenAI adapters only after an explicit workflow action."""

    load_dotenv()
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        try:
            key = str(st.secrets.get("OPENAI_API_KEY", "")).strip()
        except Exception:
            key = ""
    if not key:
        raise ValueError(
            "OPENAI_API_KEY is not configured. Add it to the environment or "
            ".streamlit/secrets.toml, then retry."
        )
    client = OpenAI(
        api_key=key,
        max_retries=0,
        timeout=config.models.timeout_seconds,
    )
    complete = make_text_completion(
        client,
        config=config.models,
        usage_tracker=st.session_state.usage_tracker,
    )
    return client, complete


def show_failure(error: Exception) -> None:
    """Show a concise failure and ensure ordinary reruns do not retry it."""

    logger.exception("Workflow action failed", exc_info=error)
    st.error(f"{type(error).__name__}: {error}")


def split_lines(value: str) -> list[str]:
    """Convert a multiline input to normalized nonblank values."""

    return [line.strip() for line in value.splitlines() if line.strip()]


def download_path(path: Path) -> None:
    """Render a download button for one existing session output."""

    if not path.is_file():
        return
    st.download_button(
        label=f"Download {path.name}",
        data=path.read_bytes(),
        file_name=path.name,
        mime="application/octet-stream",
        key=f"download-{path.resolve()}",
    )
