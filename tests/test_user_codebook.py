"""User-codebook loading, enhancement, export, and Part 2 coding tests."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from codeframe.config import LanguageConfig, ModelConfig, UserCodebookConfig
from codeframe.user_codebook import (
    apply_enhanced_codebook_part2,
    build_codebook_enhancement_requests,
    code_part2_batch,
    enhance_user_codebook_with_ai,
    load_user_codebook,
    prepare_user_codebook,
    run_user_codebook_coding,
    save_enhanced_codebook_excel,
)


def complete_entry(name: str, code_id: str) -> dict[str, Any]:
    return {
        "name": name,
        "code_id": code_id,
        "definition": f"Definition {name}",
        "inclusion_criteria": ["include one", "include two"],
        "exclusion_criteria": ["exclude"],
        "example_verbatims": ["example one", "example two"],
        "source": "user_codebook",
    }


def complete_codebook() -> dict[str, Any]:
    return {
        "version": "user-supplied+ai-enhanced",
        "multi_label": True,
        "codebook_language": "en",
        "codes": [
            complete_entry("Service", "S1"),
            complete_entry("Price", "P1"),
            complete_entry("Other / Not classifiable", "O1"),
        ],
    }


@pytest.mark.parity
def test_loader_auto_detects_columns_preserves_content_and_generates_ids(
    tmp_path: Path,
) -> None:
    path = tmp_path / "codebook.csv"
    pd.DataFrame(
        {
            "Code ID": ["SERVICE", None, "OTHER"],
            "Code Name": ["Service", "Prix élevé", "Other / Not classifiable"],
            "Definition": ["Keep exactly", "", "Catch all"],
            "Inclusion Criteria": ['["one", "two"]', "high;expensive", "none"],
            "Exclusion Criteria": ["x|y", "", "specific"],
            "Examples": ["good\nfast", "", "unknown"],
        }
    ).to_csv(path, index=False)

    result = load_user_codebook(path, language_code="en")

    assert [code["name"] for code in result["codes"]] == [
        "Service",
        "Prix élevé",
        "Other / Not classifiable",
    ]
    assert result["codes"][0]["definition"] == "Keep exactly"
    assert result["codes"][0]["inclusion_criteria"] == ["one", "two"]
    assert result["codes"][0]["exclusion_criteria"] == ["x", "y"]
    assert result["codes"][1]["code_id"] == "PRIX_ELEVE"
    assert result["generated_code_ids"] == [{"code_name": "Prix élevé", "code_id": "PRIX_ELEVE"}]


@pytest.mark.unit
def test_loader_rejects_bad_formats_missing_columns_and_duplicates(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        load_user_codebook(tmp_path / "codebook.json")

    missing = tmp_path / "missing.csv"
    pd.DataFrame({"Wrong": ["A"]}).to_csv(missing, index=False)
    with pytest.raises(ValueError, match="Required column"):
        load_user_codebook(missing)

    duplicate = tmp_path / "duplicate.csv"
    pd.DataFrame({"Code Name": ["Same", "same"]}).to_csv(duplicate, index=False)
    with pytest.raises(ValueError, match="Duplicate code name"):
        load_user_codebook(duplicate)


@pytest.mark.parity
def test_enhancement_fills_only_missing_fields_and_preserves_existing() -> None:
    codebook: dict[str, Any] = {
        "version": "user-supplied",
        "multi_label": True,
        "codebook_language": "en",
        "codes": [
            complete_entry("Complete", "C1"),
            {
                "name": "Missing",
                "code_id": "M1",
                "definition": "",
                "inclusion_criteria": [],
                "exclusion_criteria": ["existing exclusion"],
                "example_verbatims": [],
            },
        ],
    }
    observed: list[dict[str, Any]] = []

    def complete(**kwargs: Any) -> str:
        observed.append(kwargs)
        return json.dumps(
            {
                "enhancements": [
                    {
                        "code_ref": "M1",
                        "definition": "Generated definition",
                        "inclusion_criteria": ["one", "two"],
                        "example_verbatims": ["example one", "example two"],
                    }
                ]
            }
        )

    result = enhance_user_codebook_with_ai(
        complete,
        codebook,
        model_config=ModelConfig(coding_model="mock"),
        now=lambda: datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert build_codebook_enhancement_requests(codebook)[0]["code_ref"] == "code_0002"
    assert result["codes"][0] == codebook["codes"][0]
    assert result["codes"][1]["exclusion_criteria"] == ["existing exclusion"]
    assert result["codes"][1]["definition"] == "Generated definition"
    enhancement_metadata = result["enhancement_metadata"]
    assert isinstance(enhancement_metadata, dict)
    assert enhancement_metadata["generated_field_count"] == 3
    assert result["generated_at"] == "2026-01-01T00:00:00+00:00"
    assert "existing_fields_read_only" in observed[0]["messages"][1]["content"]


@pytest.mark.unit
def test_enhancement_rejects_extra_patch_fields() -> None:
    codebook = {
        "version": "user-supplied",
        "multi_label": True,
        "codes": [
            {
                "name": "Missing",
                "definition": "",
                "inclusion_criteria": [],
                "exclusion_criteria": [],
                "example_verbatims": [],
            }
        ],
    }

    def complete(**_: Any) -> str:
        return json.dumps(
            {
                "enhancements": [
                    {
                        "code_ref": "code_0001",
                        "definition": "d",
                        "inclusion_criteria": ["a"],
                        "exclusion_criteria": ["b"],
                        "example_verbatims": ["x", "y"],
                        "name": "overwrite",
                    }
                ]
            }
        )

    with pytest.raises(ValueError, match="returned fields"):
        enhance_user_codebook_with_ai(complete, codebook)


@pytest.mark.integration
def test_enhanced_excel_export_is_reimportable(tmp_path: Path) -> None:
    path = save_enhanced_codebook_excel(
        complete_codebook(),
        output_dir=tmp_path,
        file_name="enhanced.xlsx",
    )
    workbook = pd.ExcelFile(path)
    assert workbook.sheet_names == ["Codebook", "Metadata"]
    reloaded = load_user_codebook(path, sheet_name="Codebook", language_code="en")
    assert [code["code_id"] for code in reloaded["codes"]] == ["S1", "P1", "O1"]


@pytest.mark.integration
def test_part2_batch_falls_back_only_for_malformed_batch() -> None:
    outputs = [
        "bad batch",
        '["Service"]',
        '["Price"]',
    ]

    def complete(**_: Any) -> str:
        return outputs.pop(0)

    results = code_part2_batch(
        complete,
        ["good service", "too expensive"],
        complete_codebook(),
        survey_context="Context",
        question="Question?",
        config=UserCodebookConfig(part2_batch_size=2, part2_delay_seconds=0),
        sleep=lambda _: None,
    )
    assert [result["codes"][0]["code"] for result in results] == ["Service", "Price"]


@pytest.mark.parity
def test_part2_deduplicates_and_sets_nan_or_catchall_confidence() -> None:
    calls = 0

    def complete(**_: Any) -> str:
        nonlocal calls
        calls += 1
        return json.dumps(
            [
                {"response_num": 1, "codes": ["Service"]},
                {"response_num": 2, "codes": []},
            ]
        )

    dataframe = pd.DataFrame(
        {"final_text_fr": ["same", "unclear", "same"]},
    )
    result = apply_enhanced_codebook_part2(
        complete,
        dataframe,
        complete_codebook(),
        survey_context="Context",
        question="Question?",
        config=UserCodebookConfig(part2_batch_size=15, part2_delay_seconds=0),
        sleep=lambda _: None,
    )

    assert calls == 1
    assert result["code_Service"].tolist() == [1, 0, 1]
    assert result["conf_Service"].isna().all()
    assert result["code_Other / Not classifiable"].tolist() == [0, 1, 0]
    assert result["conf_Other / Not classifiable"].tolist()[1] == 0.5
    assert result["coding_status"].tolist() == ["coded", "catch_all", "coded"]
    assert set(result["coding_prompt_version"]) == {"user-codebook-coding-v1"}


@pytest.mark.e2e
def test_manual_path_part1_and_part2_end_to_end(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    pd.DataFrame(
        {
            "Code ID": ["S1", "O1"],
            "Code Name": ["Service", "Other / Not classifiable"],
            "Definition": ["Service definition", "Catch all"],
            "Inclusion Criteria": ["one;two", "none"],
            "Exclusion Criteria": ["exclude", "specific"],
            "Examples": ["a;b", "x;y"],
        }
    ).to_csv(source, index=False)
    prepared = prepare_user_codebook(
        source,
        None,
        output_dir=tmp_path,
        file_stem="fixture",
        language_config=LanguageConfig(codebook_language_code="en"),
        config=UserCodebookConfig(enhance_with_ai=False),
        name_column="Code Name",
        id_column="Code ID",
    )

    def complete(**_: Any) -> str:
        return json.dumps(
            [
                {"response_num": 1, "codes": ["Service"]},
                {"response_num": 2, "codes": []},
            ]
        )

    coded = run_user_codebook_coding(
        pd.DataFrame(
            {
                "response_id": ["R1", "R2"],
                "original_text": ["good", "unclear"],
                "final_text_fr": ["good", "unclear"],
                "is_valid": [True, True],
            }
        ),
        prepared.codebook,
        complete,
        output_dir=tmp_path,
        file_stem="fixture",
        survey_context="Context",
        question="Question?",
        config=UserCodebookConfig(part2_delay_seconds=0),
        include_charts=False,
        sleep=lambda _: None,
    )

    assert prepared.json_path.is_file()
    assert prepared.excel_path.is_file()
    assert coded.dataframe["codes"].tolist() == [
        "Service",
        "Other / Not classifiable",
    ]
    summary_report = coded.outputs["summary_report"]
    assert summary_report is not None
    assert Path(summary_report).is_file()
