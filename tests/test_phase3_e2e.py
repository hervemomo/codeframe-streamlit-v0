"""Mocked end-to-end AI-generated codebook workflow."""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import pytest

from codeframe.ai_coding import run_ai_codebook_workflow
from codeframe.config import CodingConfig


def generated_codebook() -> dict[str, Any]:
    def entry(name: str, clusters: list[int]) -> dict[str, Any]:
        return {
            "name": name,
            "definition": name,
            "inclusion_criteria": ["include"],
            "exclusion_criteria": ["exclude"],
            "example_verbatims": ["example"],
            "source_clusters": clusters,
        }

    return {
        "codes": [
            entry("Service", [1]),
            entry("Prix", [2]),
            entry("Autre / Non classifiable", []),
        ]
    }


@pytest.mark.e2e
def test_mocked_ai_pipeline_creates_coded_data_codebook_and_report(tmp_path: Path) -> None:
    dataframe = pd.DataFrame(
        {
            "response_id": [f"R{index:06d}" for index in range(1, 11)],
            "original_text": [f"response {index}" for index in range(10)],
            "final_text_fr": [f"réponse {index}" for index in range(10)],
            "is_valid": [True] * 10,
        }
    )
    labels = np.asarray([0] * 5 + [1] * 5)

    def discover(
        frame: pd.DataFrame,
        client: Any,
    ) -> tuple[pd.DataFrame, np.ndarray[Any, Any], dict[int, list[str]], dict[int, int]]:
        assert client is not None
        clustered = frame.copy()
        clustered["cluster"] = labels
        clustered["cluster_probability"] = 0.9
        return (
            clustered,
            labels,
            {0: ["service"], 1: ["prix"]},
            {0: 5, 1: 5},
        )

    calls = 0

    def complete(**kwargs: Any) -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            assert "source_clusters" in kwargs["messages"][1]["content"]
            return json.dumps(generated_codebook(), ensure_ascii=False)
        return json.dumps(
            [
                {
                    "response_num": index + 1,
                    "codes": [
                        {
                            "code": "Service" if index < 5 else "Prix",
                            "confidence": 0.9,
                        }
                    ],
                }
                for index in range(10)
            ],
            ensure_ascii=False,
        )

    result = run_ai_codebook_workflow(
        dataframe,
        SimpleNamespace(),
        complete,
        output_dir=tmp_path,
        file_stem="fixture",
        survey_context="Satisfaction",
        coding_config=CodingConfig(mode="ai", coding_batch_size=20),
        theme_discovery=discover,
        include_charts=False,
        sleep=lambda _: None,
    )

    assert result.dataframe["codes"].tolist() == ["Service"] * 5 + ["Prix"] * 5
    assert result.dataframe["num_codes"].tolist() == [1] * 10
    assert [code["estimated_response_count"] for code in result.codebook["codes"]] == [
        5,
        5,
        0,
    ]
    codebook_output = result.outputs["codebook"]
    summary_output = result.outputs["summary_report"]
    assert codebook_output is not None
    assert summary_output is not None
    assert Path(codebook_output).is_file()
    assert Path(summary_output).is_file()
    assert calls == 2


@pytest.mark.unit
def test_ai_workflow_rejects_manual_mode(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="mode 'ai'"):
        run_ai_codebook_workflow(
            pd.DataFrame(),
            SimpleNamespace(),
            lambda **_: "",
            output_dir=tmp_path,
            file_stem="fixture",
            survey_context="context",
            coding_config=CodingConfig(mode="manual"),
        )
