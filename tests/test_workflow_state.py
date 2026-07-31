from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from codeframe.config import CodingConfig, ProjectConfig
from codeframe.workflow_state import (
    begin_refinement_attempt,
    collect_output_paths,
    elapsed_seconds,
    has_downstream_results,
    initialize_workflow_state,
    project_fingerprint,
    record_output_paths,
    set_coding_result,
    set_prepared_user_codebook,
    set_preprocessed_data,
    set_refinement_result,
    survey_fingerprint,
    update_project_config,
    usage_summary,
)


def project(*, question: str = "Question?", mode: str = "manual") -> ProjectConfig:
    return ProjectConfig(
        survey_question=question,
        survey_context="Context",
        coding=CodingConfig(mode=mode),  # type: ignore[arg-type]
    )


@pytest.mark.unit
def test_initialize_and_fingerprints_are_stable() -> None:
    state: dict[str, Any] = {}
    initialize_workflow_state(state)
    started = state["session_started_at"]

    initialize_workflow_state(state)

    assert state["session_started_at"] is started
    assert project_fingerprint(project()) == project_fingerprint(project())
    assert project_fingerprint(project()) != project_fingerprint(project(question="New?"))
    assert survey_fingerprint("survey.csv", b"one") == survey_fingerprint("survey.csv", b"one")
    assert survey_fingerprint("survey.csv", b"one") != survey_fingerprint("survey.csv", b"two")


@pytest.mark.unit
def test_project_change_invalidates_all_downstream_state() -> None:
    state: dict[str, Any] = {}
    update_project_config(state, project())
    state.update(
        {
            "preprocessed_df": pd.DataFrame({"value": [1]}),
            "prepared_user_codebook": object(),
            "current_dataframe": pd.DataFrame({"value": [1]}),
            "current_codebook": {"codes": []},
            "refinement_history": ("split",),
        }
    )

    assert has_downstream_results(state)
    invalidated = update_project_config(state, project(question="Changed?"))

    assert {"preprocessed_df", "prepared_user_codebook", "current_dataframe"}.issubset(invalidated)
    assert state["preprocessed_df"] is None
    assert state["prepared_user_codebook"] is None
    assert state["current_codebook"] is None
    assert state["refinement_history"] == ()
    assert not has_downstream_results(state)


@pytest.mark.unit
def test_same_project_does_not_invalidate_results() -> None:
    state: dict[str, Any] = {}
    config = project()
    update_project_config(state, config)
    existing = pd.DataFrame({"value": [1]})
    state["preprocessed_df"] = existing

    assert update_project_config(state, config) == set()
    assert state["preprocessed_df"] is existing


@pytest.mark.unit
def test_preprocessing_invalidates_coding_but_preserves_prepared_codebook(
    tmp_path: Path,
) -> None:
    state: dict[str, Any] = {}
    set_prepared_user_codebook(state, object(), outputs={})
    state["current_dataframe"] = pd.DataFrame({"old": [1]})
    state["current_codebook"] = {"codes": [{"name": "Old"}]}
    output = tmp_path / "processed.csv"
    output.write_text("value\n1\n", encoding="utf-8")

    invalidated = set_preprocessed_data(
        state,
        pd.DataFrame({"new": [1]}),
        source_fingerprint="source",
        outputs={"processed": output},
    )

    assert "current_dataframe" in invalidated
    assert state["current_dataframe"] is None
    assert state["prepared_user_codebook"] is not None
    assert state["output_paths"] == (output,)


@pytest.mark.unit
def test_new_prepared_codebook_invalidates_coding_but_preserves_preprocessing() -> None:
    state: dict[str, Any] = {}
    preprocessed = pd.DataFrame({"cleaned_text": ["one"]})
    state["preprocessed_df"] = preprocessed
    state["current_dataframe"] = pd.DataFrame({"code_old": [1]})
    state["current_codebook"] = {"codes": [{"name": "Old"}]}

    invalidated = set_prepared_user_codebook(state, object(), outputs={})

    assert {"current_dataframe", "current_codebook"}.issubset(invalidated)
    assert state["preprocessed_df"] is preprocessed
    assert state["prepared_user_codebook"] is not None


@pytest.mark.unit
def test_alternative_coding_path_and_refinement_chain(tmp_path: Path) -> None:
    state: dict[str, Any] = {"refinement_history": ("split",)}
    coded = pd.DataFrame({"code_1": [1]})
    codebook = {"codes": [{"name": "One"}]}

    invalidated = set_coding_result(
        state,
        path="manual",
        result="coding",
        dataframe=coded,
        codebook=codebook,
        outputs={},
    )
    assert "refinement_history" in invalidated
    assert state["active_path"] == "manual"
    assert state["current_dataframe"] is coded

    begin_refinement_attempt(state, "split")
    assert state["last_refinement_result"] is None
    refined = pd.DataFrame({"code_2": [1]})
    refined_codebook = {"codes": [{"name": "Two"}]}
    output = tmp_path / "split.xlsx"
    output.write_text("report", encoding="utf-8")
    set_refinement_result(
        state,
        kind="split",
        result="split result",
        dataframe=refined,
        codebook=refined_codebook,
        outputs=[{"report": str(output)}],
    )
    set_refinement_result(
        state,
        kind="merge",
        result="merge result",
        dataframe=refined,
        codebook=refined_codebook,
        outputs={},
    )

    assert state["current_dataframe"] is refined
    assert state["current_codebook"] is refined_codebook
    assert state["refinement_history"] == ("split", "merge")
    assert state["output_paths"] == (output,)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda state: begin_refinement_attempt(state, "bad"), "kind"),
        (
            lambda state: set_coding_result(
                state,
                path="bad",
                result=None,
                dataframe=pd.DataFrame(),
                codebook={"codes": []},
                outputs={},
            ),
            "path",
        ),
    ],
)
def test_state_rejects_invalid_transition_names(
    call: Any,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        call({})


@pytest.mark.unit
def test_output_collection_recurses_deduplicates_and_ignores_text(tmp_path: Path) -> None:
    first = tmp_path / "first.csv"
    second = tmp_path / "second.xlsx"
    first.write_text("one", encoding="utf-8")
    second.write_text("two", encoding="utf-8")
    nested = {
        "one": str(first),
        "nested": [first, ({"two": second}, "ordinary response text")],
        "missing": tmp_path / "missing.csv",
    }

    assert collect_output_paths(nested) == (first, second, tmp_path / "missing.csv")
    state: dict[str, Any] = {}
    assert record_output_paths(state, nested) == (first, second)


@pytest.mark.unit
def test_usage_summary_and_elapsed_time() -> None:
    usage = pd.DataFrame(
        [
            {
                "model": "b",
                "prompt_tokens": 2,
                "completion_tokens": 3,
                "total_tokens": 5,
            },
            {
                "model": "a",
                "prompt_tokens": 7,
                "completion_tokens": 11,
                "total_tokens": 18,
            },
            {
                "model": "b",
                "prompt_tokens": 13,
                "completion_tokens": 17,
                "total_tokens": 30,
            },
        ]
    )

    summary = usage_summary(usage)

    assert summary.to_dict("records") == [
        {
            "model": "a",
            "prompt_tokens": 7,
            "completion_tokens": 11,
            "total_tokens": 18,
            "calls": 1,
        },
        {
            "model": "b",
            "prompt_tokens": 15,
            "completion_tokens": 20,
            "total_tokens": 35,
            "calls": 2,
        },
    ]
    assert list(usage_summary(pd.DataFrame()).columns) == list(summary.columns)

    started = datetime(2026, 1, 1, tzinfo=UTC)
    assert elapsed_seconds({"session_started_at": started}, now=started + timedelta(seconds=9)) == 9
    assert elapsed_seconds({"session_started_at": started}, now=started - timedelta(seconds=1)) == 0
    assert elapsed_seconds({}) == 0


@pytest.mark.unit
def test_usage_summary_rejects_incomplete_schema() -> None:
    with pytest.raises(ValueError, match="missing columns"):
        usage_summary(pd.DataFrame({"model": ["x"]}))
