"""Frequency, co-occurrence, workbook, chart, and CSV export tests."""

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from codeframe.codebook import add_codes_column
from codeframe.exports import save_preprocessed_csv
from codeframe.reporting import (
    calculate_frequencies,
    generate_cooccurrence_matrix,
    generate_reports,
    plot_cooccurrence_heatmap,
)


def sample_codebook(*, with_ids: bool = False) -> dict[str, Any]:
    """Create a compact notebook-shaped codebook fixture."""

    codes: list[dict[str, Any]] = [
        {
            "name": "Taste",
            "definition": "Taste response",
            "inclusion_criteria": ["Mentions flavor"],
            "exclusion_criteria": ["Only price"],
            "example_verbatims": ["Very tasty"],
            "source": "fixture",
        },
        {
            "name": "Price",
            "definition": "Price response",
            "inclusion_criteria": ["Mentions price"],
            "exclusion_criteria": [],
            "example_verbatims": ["Good price"],
            "source": "fixture",
        },
        {
            "name": "Other",
            "definition": "Catch-all",
            "inclusion_criteria": [],
            "exclusion_criteria": [],
            "example_verbatims": [],
            "source": "system_catch_all",
        },
    ]
    if with_ids:
        for code, identifier in zip(codes, ["T", "P", "O"], strict=True):
            code["code_id"] = identifier
    return {"codes": codes, "multi_label": True}


def coded_dataframe() -> pd.DataFrame:
    """Create coded rows with notebook assignment/confidence columns."""

    return pd.DataFrame(
        {
            "response_id": [1, 2, 3, 4],
            "original_text": ["tasty", "cheap", "tasty cheap", "unknown"],
            "final_text_fr": ["savoureux", "bon prix", "bon et prix", "inconnu"],
            "code_Taste": [1, 0, 1, 0],
            "conf_Taste": [0.9, 0.0, 0.8, 0.0],
            "code_Price": [0, 1, 1, 0],
            "conf_Price": [0.0, 0.9, 0.7, 0.0],
            "code_Other": [0, 0, 0, 1],
            "conf_Other": [0.0, 0.0, 0.0, 0.5],
        }
    )


@pytest.mark.unit
def test_add_codes_column_preserves_codebook_order_and_ids() -> None:
    dataframe = coded_dataframe()
    dataframe["codes"] = "stale"

    result = add_codes_column(dataframe, sample_codebook(with_ids=True))

    assert result["codes"].tolist() == [
        "Taste",
        "Price",
        "Taste | Price",
        "Other",
    ]
    assert result["code_ids"].tolist() == ["T", "P", "T | P", "O"]
    assert result["num_codes"].tolist() == [1, 1, 2, 1]
    assert result["has_multi_label"].tolist() == [False, False, True, False]
    assert "codes_list" not in result.columns
    assert "code_ids_list" not in result.columns


@pytest.mark.parity
def test_frequency_and_cooccurrence_math() -> None:
    dataframe = coded_dataframe()
    codebook = sample_codebook()

    frequencies = calculate_frequencies(dataframe, codebook)
    cooccurrence = generate_cooccurrence_matrix(dataframe, codebook)

    assert frequencies.to_dict("records") == [
        {"code": "Taste", "count": 2, "percentage": 50.0},
        {"code": "Price", "count": 2, "percentage": 50.0},
        {"code": "Other", "count": 1, "percentage": 25.0},
    ]
    assert cooccurrence.loc["Taste", "Taste"] == 2
    assert cooccurrence.loc["Taste", "Price"] == 1
    assert cooccurrence.loc["Other", "Price"] == 0
    assert cooccurrence.equals(cooccurrence.T)


@pytest.mark.unit
def test_frequency_includes_ids_only_for_governed_codebook() -> None:
    frequencies = calculate_frequencies(coded_dataframe(), sample_codebook(with_ids=True))

    assert frequencies.columns.tolist() == [
        "code_id",
        "code",
        "count",
        "percentage",
    ]
    assert frequencies["code_id"].tolist() == ["T", "P", "O"]


@pytest.mark.unit
def test_empty_assignment_contract(tmp_path: Path) -> None:
    dataframe = pd.DataFrame({"response_id": [1]})
    codebook = sample_codebook()

    assert calculate_frequencies(dataframe, codebook).empty
    matrix = generate_cooccurrence_matrix(dataframe, codebook)
    assert matrix.empty
    assert (
        plot_cooccurrence_heatmap(
            matrix,
            output_dir=tmp_path,
            file_stem="survey",
        )
        is None
    )


@pytest.mark.integration
def test_generate_reports_matches_workbook_and_chart_contract(tmp_path: Path) -> None:
    dataframe = add_codes_column(coded_dataframe(), sample_codebook(with_ids=True))
    outputs = generate_reports(
        dataframe,
        sample_codebook(with_ids=True),
        output_dir=tmp_path,
        file_stem="survey",
        text_column="final_text_fr",
        output_file="coding.xlsx",
    )

    assert outputs == {
        "frequency_chart": str(tmp_path / "survey_frequencies.png"),
        "cooccurrence_chart": str(tmp_path / "survey_cooccurrence.png"),
        "summary_report": str(tmp_path / "coding.xlsx"),
    }
    assert all(path and Path(path).is_file() for path in outputs.values())

    workbook = pd.ExcelFile(tmp_path / "coding.xlsx")
    assert workbook.sheet_names == [
        "Summary",
        "Frequencies",
        "Co-occurrence",
        "Codebook",
        "Coded Data",
    ]
    summary = pd.read_excel(tmp_path / "coding.xlsx", sheet_name="Summary")
    assert summary.to_dict("records") == [
        {"Metric": "Total responses", "Value": 4},
        {"Metric": "Valid responses", "Value": 4},
        {"Metric": "Invalid/blank", "Value": 0},
        {"Metric": "Coded responses", "Value": 4},
        {"Metric": "Uncoded responses", "Value": 0},
        {"Metric": "Number of codes", "Value": 3},
        {"Metric": "Multi-label", "Value": True},
    ]
    coded = pd.read_excel(tmp_path / "coding.xlsx", sheet_name="Coded Data")
    assert coded.columns.tolist() == [
        "response_id",
        "original_text",
        "codes",
        "code_ids",
        "has_multi_label",
        "num_codes",
        "final_text_fr",
        "code_Taste",
        "code_Price",
        "code_Other",
    ]
    codebook_sheet = pd.read_excel(tmp_path / "coding.xlsx", sheet_name="Codebook")
    assert codebook_sheet.columns.tolist() == [
        "Code ID",
        "Code",
        "Definition",
        "Inclusion",
        "Exclusion",
        "Examples",
        "Parent",
        "Parent Code ID",
        "Merged From",
        "Merged From IDs",
        "Source",
        "Estimated Response Count",
    ]


@pytest.mark.integration
def test_preprocessed_csv_uses_notebook_filename(tmp_path: Path) -> None:
    dataframe = pd.DataFrame({"response_id": [1], "final_text_fr": ["bonjour"]})

    destination = save_preprocessed_csv(
        dataframe,
        output_dir=tmp_path / "nested",
        file_stem="survey",
    )

    assert destination == tmp_path / "nested" / "survey_processed.csv"
    assert pd.read_csv(destination).to_dict("records") == [
        {"response_id": 1, "final_text_fr": "bonjour"}
    ]
