"""Framework-neutral workflow state transitions for the Streamlit application."""

from __future__ import annotations

import json
from collections.abc import Mapping, MutableMapping
from dataclasses import asdict
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

import pandas as pd

from codeframe.codebook import CodebookMapping
from codeframe.config import ProjectConfig

PROJECT_DOWNSTREAM_KEYS = frozenset(
    {
        "survey_source_fingerprint",
        "preprocessed_df",
        "preprocessing_outputs",
        "prepared_user_codebook",
        "coding_result",
        "active_path",
        "current_dataframe",
        "current_codebook",
        "refinement_history",
        "last_refinement_result",
        "last_refinement_kind",
    }
)

PREPROCESSING_DOWNSTREAM_KEYS = frozenset(
    {
        "coding_result",
        "active_path",
        "current_dataframe",
        "current_codebook",
        "refinement_history",
        "last_refinement_result",
        "last_refinement_kind",
    }
)

CODING_DOWNSTREAM_KEYS = frozenset(
    {
        "refinement_history",
        "last_refinement_result",
        "last_refinement_kind",
    }
)

DEFAULT_STATE: Mapping[str, Any] = {
    "project_config": None,
    "project_fingerprint": None,
    "survey_source_fingerprint": None,
    "preprocessed_df": None,
    "preprocessing_outputs": None,
    "prepared_user_codebook": None,
    "coding_result": None,
    "active_path": None,
    "current_dataframe": None,
    "current_codebook": None,
    "refinement_history": (),
    "last_refinement_result": None,
    "last_refinement_kind": None,
    "output_paths": (),
    "session_started_at": None,
}


def initialize_workflow_state(state: MutableMapping[str, Any]) -> None:
    """Populate missing application state without replacing existing values."""

    for key, value in DEFAULT_STATE.items():
        if key not in state:
            state[key] = value
    if state["session_started_at"] is None:
        state["session_started_at"] = datetime.now(UTC)


def project_fingerprint(config: ProjectConfig) -> str:
    """Return a stable non-secret fingerprint for project configuration."""

    payload = json.dumps(asdict(config), sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


def survey_fingerprint(filename: str, content: bytes) -> str:
    """Return a stable source fingerprint without retaining survey content."""

    digest = sha256()
    digest.update(Path(filename).name.encode("utf-8"))
    digest.update(b"\0")
    digest.update(content)
    return digest.hexdigest()


def update_project_config(
    state: MutableMapping[str, Any],
    config: ProjectConfig,
) -> set[str]:
    """Save project configuration and invalidate all dependent state when changed."""

    initialize_workflow_state(state)
    fingerprint = project_fingerprint(config)
    invalidated: set[str] = set()
    if state["project_fingerprint"] not in {None, fingerprint}:
        invalidated = _clear_keys(state, PROJECT_DOWNSTREAM_KEYS)
    state["project_config"] = config
    state["project_fingerprint"] = fingerprint
    return invalidated


def set_preprocessed_data(
    state: MutableMapping[str, Any],
    dataframe: pd.DataFrame,
    *,
    source_fingerprint: str,
    outputs: object,
) -> set[str]:
    """Store preprocessing results and clear stale coding/refinement results."""

    initialize_workflow_state(state)
    invalidated = _clear_keys(state, PREPROCESSING_DOWNSTREAM_KEYS)
    state["preprocessed_df"] = dataframe
    state["preprocessing_outputs"] = outputs
    state["survey_source_fingerprint"] = source_fingerprint
    record_output_paths(state, outputs)
    return invalidated


def set_prepared_user_codebook(
    state: MutableMapping[str, Any],
    prepared: object,
    *,
    outputs: object,
) -> set[str]:
    """Store a prepared codebook and invalidate dependent manual coding results."""

    initialize_workflow_state(state)
    invalidated = _clear_keys(state, PREPROCESSING_DOWNSTREAM_KEYS)
    state["prepared_user_codebook"] = prepared
    record_output_paths(state, outputs)
    return invalidated


def set_coding_result(
    state: MutableMapping[str, Any],
    *,
    path: str,
    result: object,
    dataframe: pd.DataFrame,
    codebook: CodebookMapping,
    outputs: object,
) -> set[str]:
    """Select one alternative coding path as the active refinement input."""

    if path not in {"ai", "manual"}:
        raise ValueError("path must be 'ai' or 'manual'")
    initialize_workflow_state(state)
    invalidated = _clear_keys(state, CODING_DOWNSTREAM_KEYS)
    state["coding_result"] = result
    state["active_path"] = path
    state["current_dataframe"] = dataframe
    state["current_codebook"] = codebook
    record_output_paths(state, outputs)
    return invalidated


def begin_refinement_attempt(state: MutableMapping[str, Any], kind: str) -> None:
    """Clear the previous operation result before a new split or merge attempt."""

    if kind not in {"split", "merge"}:
        raise ValueError("kind must be 'split' or 'merge'")
    initialize_workflow_state(state)
    state["last_refinement_result"] = None
    state["last_refinement_kind"] = kind


def set_refinement_result(
    state: MutableMapping[str, Any],
    *,
    kind: str,
    result: object,
    dataframe: pd.DataFrame,
    codebook: CodebookMapping,
    outputs: object,
) -> None:
    """Promote a confirmed refinement result for subsequent split/merge chaining."""

    if kind not in {"split", "merge"}:
        raise ValueError("kind must be 'split' or 'merge'")
    initialize_workflow_state(state)
    state["current_dataframe"] = dataframe
    state["current_codebook"] = codebook
    state["last_refinement_result"] = result
    state["last_refinement_kind"] = kind
    history = list(state["refinement_history"] or ())
    history.append(kind)
    state["refinement_history"] = tuple(history)
    record_output_paths(state, outputs)


def record_output_paths(state: MutableMapping[str, Any], value: object) -> tuple[Path, ...]:
    """Add existing output paths, recursively and in first-seen order."""

    initialize_workflow_state(state)
    combined = [*state["output_paths"], *collect_output_paths(value)]
    unique: list[Path] = []
    seen: set[str] = set()
    for path in combined:
        key = str(path.resolve())
        if key not in seen and path.is_file():
            unique.append(path)
            seen.add(key)
    state["output_paths"] = tuple(unique)
    return tuple(unique)


def collect_output_paths(value: object) -> tuple[Path, ...]:
    """Recursively flatten path-like report outputs while ignoring arbitrary text."""

    discovered: list[Path] = []

    def visit(candidate: object) -> None:
        if isinstance(candidate, Path):
            discovered.append(candidate)
        elif isinstance(candidate, Mapping):
            for nested in candidate.values():
                visit(nested)
        elif isinstance(candidate, (list, tuple)):
            for nested in candidate:
                visit(nested)
        elif isinstance(candidate, str):
            path = Path(candidate)
            if path.is_file():
                discovered.append(path)

    visit(value)
    unique: list[Path] = []
    seen: set[str] = set()
    for path in discovered:
        key = str(path.resolve())
        if key not in seen:
            unique.append(path)
            seen.add(key)
    return tuple(unique)


def usage_summary(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Aggregate the notebook-style usage log by model."""

    columns = [
        "model",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "calls",
    ]
    if dataframe.empty:
        return pd.DataFrame(columns=columns)
    required = {"model", "prompt_tokens", "completion_tokens", "total_tokens"}
    missing = required.difference(dataframe.columns)
    if missing:
        raise ValueError(f"Usage dataframe is missing columns: {sorted(missing)}")
    grouped = (
        dataframe.groupby("model", as_index=False)
        .agg(
            prompt_tokens=("prompt_tokens", "sum"),
            completion_tokens=("completion_tokens", "sum"),
            total_tokens=("total_tokens", "sum"),
            calls=("model", "size"),
        )
        .sort_values("model")
        .reset_index(drop=True)
    )
    return grouped[columns]


def elapsed_seconds(state: Mapping[str, Any], *, now: datetime | None = None) -> float:
    """Return non-negative elapsed session time."""

    started = state.get("session_started_at")
    if not isinstance(started, datetime):
        return 0.0
    current = now or datetime.now(UTC)
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    return max(0.0, (current - started).total_seconds())


def has_downstream_results(state: Mapping[str, Any]) -> bool:
    """Report whether a project change would discard completed downstream work."""

    for key in PROJECT_DOWNSTREAM_KEYS:
        value = state.get(key)
        if value is not None and not (isinstance(value, tuple) and not value):
            return True
    return False


def _clear_keys(state: MutableMapping[str, Any], keys: frozenset[str]) -> set[str]:
    invalidated: set[str] = set()
    for key in keys:
        previous = state.get(key)
        is_empty_tuple = isinstance(previous, tuple) and not previous
        if previous is not None and not is_empty_tuple:
            invalidated.add(key)
        state[key] = DEFAULT_STATE[key]
    return invalidated
