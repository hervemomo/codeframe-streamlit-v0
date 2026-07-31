"""Notebook-parity tests for survey loading, cleaning, filtering, and audit output."""

from pathlib import Path

import pandas as pd
import pytest

from codeframe.loaders import load_survey_data
from codeframe.preprocessing import (
    clean_text,
    is_valid_response,
    partition_preprocessed_records,
    preprocess_data,
)


@pytest.mark.unit
def test_clean_text_preserves_notebook_operation_order() -> None:
    raw = "<b>CafÃ© &amp; goût</b>\x00 https://example.com person@example.com 😀"

    assert clean_text(raw) == "Café & goût __URL__ __EMAIL__"
    assert (
        clean_text(
            "Été 😀",
            emoji_handling="token",
            lowercase=True,
            strip_accents=True,
        )
        == "ete __emoji__"
    )
    assert clean_text(None) == ""
    assert clean_text(pd.NA) == ""
    assert clean_text(42) == "42"


@pytest.mark.unit
@pytest.mark.parametrize(
    "text",
    [
        "",
        "aucun",
        "Je ne sais pas",
        "...",
        "__URL__",
        "seul",
    ],
)
def test_invalid_response_contract(text: str) -> None:
    assert not is_valid_response(text)


@pytest.mark.unit
def test_valid_response_word_threshold_is_configurable() -> None:
    assert is_valid_response("bon goût")
    assert not is_valid_response("délicieux")
    assert is_valid_response("délicieux", min_words=1)


@pytest.mark.unit
def test_csv_loader_drops_blanks_after_preserving_metadata(tmp_path: Path) -> None:
    source = tmp_path / "survey.csv"
    pd.DataFrame(
        {
            "source_id": ["A", "B", "C", "D"],
            "feedback": ["Bon goût", None, "  ", "Prix correct"],
            "segment": ["x", "y", "z", "x"],
        }
    ).to_csv(source, index=False)

    loaded = load_survey_data(source, "feedback")

    assert loaded.index.tolist() == [0, 3]
    assert loaded["response_id"].tolist() == [1, 2]
    assert loaded["original_text"].tolist() == ["Bon goût", "Prix correct"]
    assert loaded["segment"].tolist() == ["x", "x"]


@pytest.mark.unit
def test_loader_preserves_selected_ids_and_excel_sheet(tmp_path: Path) -> None:
    source = tmp_path / "survey.xlsx"
    with pd.ExcelWriter(source, engine="openpyxl") as writer:
        pd.DataFrame({"feedback": ["wrong"]}).to_excel(writer, sheet_name="Other", index=False)
        pd.DataFrame({"respondent": [101, 102], "feedback": ["Très bon", "Bon prix"]}).to_excel(
            writer, sheet_name="Responses", index=False
        )

    loaded = load_survey_data(
        source,
        "feedback",
        sheet_name="Responses",
        id_column="respondent",
    )

    assert loaded["response_id"].tolist() == [101, 102]
    assert loaded["original_text"].tolist() == ["Très bon", "Bon prix"]


@pytest.mark.unit
def test_loader_reports_available_columns(tmp_path: Path) -> None:
    source = tmp_path / "survey.csv"
    pd.DataFrame({"answer": ["value"]}).to_csv(source, index=False)

    with pytest.raises(ValueError, match="Available.*answer"):
        load_survey_data(source, "feedback")


@pytest.mark.parity
def test_partition_preserves_invalid_duplicate_overlap() -> None:
    dataframe = pd.DataFrame(
        {
            "response_id": [1, 2, 3, 4, 5],
            "original_text": [
                "Bon goût",
                "Bon goût",
                "aucun",
                "aucun",
                "Prix correct",
            ],
        }
    )

    retained, invalid, duplicates = partition_preprocessed_records(dataframe)

    assert retained["response_id"].tolist() == [1, 5]
    assert invalid["response_id"].tolist() == [3, 4]
    assert duplicates["response_id"].tolist() == [2, 4]
    assert retained.columns.tolist() == [
        "response_id",
        "original_text",
        "cleaned_text",
    ]


@pytest.mark.integration
def test_preprocess_writes_notebook_audit_and_detection_columns(
    tmp_path: Path,
) -> None:
    dataframe = pd.DataFrame(
        {
            "response_id": [1, 2, 3, 4],
            "original_text": ["Bon goût", "Bon goût", "aucun", "Good price"],
        }
    )

    def detector(value: object) -> tuple[str, str, float | None]:
        return ("en", "detected", 0.95) if str(value) == "Good price" else ("fr", "detected", 0.99)

    result = preprocess_data(
        dataframe,
        output_dir=tmp_path,
        detector=detector,
    )

    assert result["response_id"].tolist() == [1, 4]
    assert result["detected_lang"].tolist() == ["fr", "en"]
    assert result["detected_lang_status"].tolist() == ["detected", "detected"]
    assert result["detected_lang_confidence"].tolist() == [0.99, 0.95]

    audit = tmp_path / "removed_records.xlsx"
    assert audit.is_file()
    workbook = pd.ExcelFile(audit)
    assert workbook.sheet_names == ["Invalid Records", "Duplicate Records"]
    invalid = pd.read_excel(audit, sheet_name="Invalid Records")
    duplicates = pd.read_excel(audit, sheet_name="Duplicate Records")
    assert invalid["response_id"].tolist() == [3]
    assert duplicates["response_id"].tolist() == [2]
    assert {"cleaned_text", "is_valid", "is_duplicate"} <= set(invalid.columns)


@pytest.mark.unit
def test_preprocess_skips_audit_when_nothing_is_removed(tmp_path: Path) -> None:
    dataframe = pd.DataFrame(
        {
            "response_id": [1, 2],
            "original_text": ["Bon goût", "Prix correct"],
        }
    )

    preprocess_data(
        dataframe,
        output_dir=tmp_path,
        detector=lambda _: ("fr", "detected", 0.9),
    )

    assert not (tmp_path / "removed_records.xlsx").exists()
