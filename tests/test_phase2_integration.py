"""Mocked end-to-end Phase 2 workflow across loading, preprocessing, and reports."""

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from codeframe.codebook import add_codes_column
from codeframe.exports import save_preprocessed_csv
from codeframe.loaders import load_survey_data
from codeframe.preprocessing import preprocess_data
from codeframe.reporting import generate_reports
from codeframe.translation import translate_source_records


@pytest.mark.integration
@pytest.mark.parity
def test_phase2_pipeline_with_mocked_translation(tmp_path: Path) -> None:
    survey = tmp_path / "survey.csv"
    pd.DataFrame(
        {
            "feedback": [
                "Bon goût",
                "Good price",
                "Bon goût",
                "aucun",
                None,
            ],
            "segment": ["a", "b", "a", "b", "c"],
        }
    ).to_csv(survey, index=False)
    loaded = load_survey_data(survey, "feedback")

    def detector(value: object) -> tuple[str, str, float | None]:
        if str(value) == "Good price":
            return "en", "detected", 0.99
        return "fr", "detected", 0.99

    preprocessed = preprocess_data(
        loaded,
        output_dir=tmp_path / "audit",
        detector=detector,
    )

    def translator(
        texts: Sequence[str],
        *,
        source_language_name: str | None,
        target_language_name: str,
    ) -> list[str]:
        assert source_language_name == "English"
        assert target_language_name == "French"
        return ["Bon prix" if text == "Good price" else text for text in texts]

    translated = translate_source_records(
        preprocessed,
        translator,
        delay=0,
        sleep=lambda _: None,
    )
    processed_path = save_preprocessed_csv(
        translated,
        output_dir=tmp_path / "exports",
        file_stem="survey",
    )

    assert translated["response_id"].tolist() == [1, 2]
    assert translated["final_text_fr"].tolist() == ["Bon goût", "Bon prix"]
    assert translated["translation_status"].tolist() == [
        "not_required",
        "translated",
    ]
    assert processed_path.is_file()

    codebook: dict[str, Any] = {
        "codes": [
            {
                "name": "Taste",
                "definition": "Taste",
                "inclusion_criteria": [],
                "exclusion_criteria": [],
                "example_verbatims": [],
            },
            {
                "name": "Price",
                "definition": "Price",
                "inclusion_criteria": [],
                "exclusion_criteria": [],
                "example_verbatims": [],
            },
        ],
        "multi_label": False,
    }
    translated["code_Taste"] = [1, 0]
    translated["conf_Taste"] = [0.9, 0.0]
    translated["code_Price"] = [0, 1]
    translated["conf_Price"] = [0.0, 0.9]
    add_codes_column(translated, codebook)
    outputs = generate_reports(
        translated,
        codebook,
        output_dir=tmp_path / "reports",
        file_stem="survey",
        text_column="final_text_fr",
        include_charts=False,
        output_file="phase2.xlsx",
    )

    assert outputs == {"summary_report": str(tmp_path / "reports" / "phase2.xlsx")}
    frequencies = pd.read_excel(outputs["summary_report"], sheet_name="Frequencies")
    assert frequencies.to_dict("records") == [
        {"code": "Taste", "count": 1, "percentage": 50},
        {"code": "Price", "count": 1, "percentage": 50},
    ]
