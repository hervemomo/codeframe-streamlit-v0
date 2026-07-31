from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from codeframe.config import CodingConfig, ProjectConfig

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.integration
def test_project_setup_saves_selected_alternative_path() -> None:
    app = AppTest.from_file(str(ROOT / "app.py"))
    app.run(timeout=30)

    app.text_area[0].input("How was the experience?")
    app.text_area[1].input("Customer satisfaction study")
    app.radio[0].set_value("ai")
    next(button for button in app.button if button.label == "Save project setup").click()
    app.run(timeout=30)

    assert not app.exception
    config = app.session_state["project_config"]
    assert isinstance(config, ProjectConfig)
    assert config.coding.mode == "ai"
    assert any("Project setup saved" in success.value for success in app.success)


@pytest.mark.integration
@pytest.mark.parametrize(
    "relative_path",
    [
        "pages/1_Preprocessing.py",
        "pages/2_AI_Codebook.py",
        "pages/3_User_Codebook.py",
        "pages/4_Refinement.py",
        "pages/5_Results_and_Downloads.py",
    ],
)
def test_dependent_pages_render_safe_prerequisite_message(relative_path: str) -> None:
    app = AppTest.from_file(str(ROOT / relative_path))

    app.run(timeout=30)

    assert not app.exception
    assert app.info


def _refinement_state() -> dict[str, Any]:
    dataframe = pd.DataFrame(
        {
            "response_id": ["R1", "R2"],
            "final_text_fr": ["one", "two"],
            "code_A": [1, 0],
            "conf_A": [0.9, 0.0],
            "code_B": [0, 1],
            "conf_B": [0.0, 0.8],
            "num_codes": [1, 1],
        }
    )
    codebook = {
        "codes": [
            {"name": "A", "definition": "A"},
            {"name": "B", "definition": "B"},
        ],
        "multi_label": True,
    }
    return {
        "project_config": ProjectConfig(
            survey_question="Question?",
            survey_context="Context",
            coding=CodingConfig(mode="manual"),
        ),
        "current_dataframe": dataframe,
        "current_codebook": codebook,
        "active_path": "manual",
    }


@pytest.mark.integration
def test_ai_page_runs_only_after_explicit_action_and_promotes_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataframe = _refinement_state()["current_dataframe"]
    codebook = _refinement_state()["current_codebook"]
    calls = 0

    def fake_workflow(*_: Any, **__: Any) -> SimpleNamespace:
        nonlocal calls
        calls += 1
        return SimpleNamespace(dataframe=dataframe, codebook=codebook, outputs={})

    monkeypatch.setattr(
        "ui.common.api_services",
        lambda _: (SimpleNamespace(), lambda **__: ""),
    )
    monkeypatch.setattr("codeframe.ai_coding.run_ai_codebook_workflow", fake_workflow)
    app = AppTest.from_file(str(ROOT / "pages" / "2_AI_Codebook.py"))
    app.session_state["project_config"] = ProjectConfig(
        survey_question="Question?",
        survey_context="Context",
        coding=CodingConfig(mode="ai"),
    )
    app.session_state["preprocessed_df"] = dataframe
    app.run(timeout=30)

    assert calls == 0
    next(
        button for button in app.button if button.label == "Generate codebook and code responses"
    ).click()
    app.run(timeout=30)

    assert not app.exception
    assert calls == 1
    assert app.session_state["active_path"] == "ai"
    assert app.session_state["current_dataframe"] is dataframe


@pytest.mark.integration
def test_user_codebook_part2_explicit_action_promotes_manual_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state = _refinement_state()
    dataframe = state["current_dataframe"]
    codebook = state["current_codebook"]
    codebook_json = tmp_path / "prepared.json"
    codebook_excel = tmp_path / "prepared.xlsx"
    codebook_json.write_text("{}", encoding="utf-8")
    codebook_excel.write_bytes(b"workbook")
    prepared = SimpleNamespace(
        codebook=codebook,
        json_path=codebook_json,
        excel_path=codebook_excel,
    )
    calls = 0

    def fake_coding(*_: Any, **__: Any) -> SimpleNamespace:
        nonlocal calls
        calls += 1
        return SimpleNamespace(dataframe=dataframe, codebook=codebook, outputs={})

    monkeypatch.setattr(
        "ui.common.api_services",
        lambda _: (SimpleNamespace(), lambda **__: ""),
    )
    monkeypatch.setattr("codeframe.user_codebook.run_user_codebook_coding", fake_coding)
    app = AppTest.from_file(str(ROOT / "pages" / "3_User_Codebook.py"))
    app.session_state["project_config"] = state["project_config"]
    app.session_state["preprocessed_df"] = dataframe
    app.session_state["prepared_user_codebook"] = prepared
    app.run(timeout=30)

    assert calls == 0
    next(
        button for button in app.button if button.label == "Code responses with prepared codebook"
    ).click()
    app.run(timeout=30)

    assert not app.exception
    assert calls == 1
    assert app.session_state["active_path"] == "manual"


@pytest.mark.integration
def test_unconfirmed_split_does_not_change_active_result_or_call_api() -> None:
    app = AppTest.from_file(str(ROOT / "pages" / "4_Refinement.py"))
    for key, value in _refinement_state().items():
        app.session_state[key] = value
    original = app.session_state["current_dataframe"]
    app.run(timeout=30)

    next(button for button in app.button if button.label == "Apply split").click()
    app.run(timeout=30)

    assert not app.exception
    pd.testing.assert_frame_equal(app.session_state["current_dataframe"], original)
    assert app.session_state["last_refinement_result"] is None
    assert any("No split was run" in info.value for info in app.info)


@pytest.mark.integration
def test_results_page_renders_summary_without_model_calls() -> None:
    app = AppTest.from_file(str(ROOT / "pages" / "5_Results_and_Downloads.py"))
    for key, value in _refinement_state().items():
        app.session_state[key] = value

    app.run(timeout=30)

    assert not app.exception
    assert any(metric.label == "Responses" and metric.value == "2" for metric in app.metric)
    assert any("No model requests" in info.value for info in app.info)
