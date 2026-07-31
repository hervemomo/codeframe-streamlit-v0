"""Batch coding, normalization, fallback, and dataframe assignment tests."""

import json
from typing import Any

import pandas as pd
import pytest

from codeframe.ai_coding import (
    apply_codes_to_dataframe,
    code_batch,
    deduplicate_texts,
    normalize_coding_result,
)
from codeframe.config import CodingConfig


def codebook(*, multi_label: bool = True) -> dict[str, Any]:
    def entry(name: str, code_id: str = "") -> dict[str, Any]:
        value: dict[str, Any] = {
            "name": name,
            "definition": name,
            "inclusion_criteria": ["include"],
            "exclusion_criteria": ["exclude"],
            "example_verbatims": [],
        }
        if code_id:
            value["code_id"] = code_id
        return value

    return {
        "codes": [
            entry("Service", "S1"),
            entry("Price", "P1"),
            entry("Other / Not classifiable", "O1"),
        ],
        "multi_label": multi_label,
        "codebook_language": "en",
    }


@pytest.mark.unit
def test_deduplication_preserves_expansion_map() -> None:
    assert deduplicate_texts(["a", "b", "a"]) == (["a", "b"], [0, 1, 0])


@pytest.mark.parity
def test_normalization_preserves_order_maps_ids_and_audits_drops() -> None:
    raw = {
        "reasoning": "brief",
        "codes": [
            {"code": "P1", "confidence": "1.5"},
            {"code": "Other / Not classifiable", "confidence": 0.9},
            {"code": "P1", "confidence": 0.2},
            {"code": "Service", "confidence": "bad"},
            {"code": "invalid"},
        ],
    }
    result = normalize_coding_result(raw, codebook(), configured_max=1)

    assert result["codes"] == [{"code": "Price", "confidence": 1.0}]
    assert result["duplicate_returned_codes"] == ["Price"]
    assert result["invalid_returned_codes"] == ["invalid"]
    assert result["dropped_due_to_max_codes"] == ["Service"]
    assert result["removed_catch_all_from_mixed_selection"] is True
    assert result["reasoning"] == "brief"


@pytest.mark.parity
def test_zero_valid_codes_gets_exclusive_half_confidence_fallback() -> None:
    result = normalize_coding_result({"codes": [{"code": "unknown"}]}, codebook())
    assert result["codes"] == [
        {
            "code": "Other / Not classifiable",
            "confidence": 0.5,
            "fallback": True,
        }
    ]
    assert result["max_codes_per_response"] == 3


@pytest.mark.unit
def test_single_label_forces_one_assignment() -> None:
    result = normalize_coding_result(
        {"codes": [{"code": "Service"}, {"code": "Price"}]},
        codebook(multi_label=False),
    )
    assert [selection["code"] for selection in result["codes"]] == ["Service"]
    assert result["max_codes_per_response"] == 1


@pytest.mark.integration
def test_batch_codes_unique_texts_once_and_expands_duplicates() -> None:
    calls: list[dict[str, Any]] = []

    def complete(**kwargs: Any) -> str:
        calls.append(kwargs)
        return json.dumps(
            [
                {"response_num": 1, "codes": [{"code": "Service", "confidence": 0.8}]},
                {"response_num": 2, "codes": [{"code": "Price", "confidence": 0.7}]},
            ]
        )

    results = code_batch(
        complete,
        ["same", "different", "same"],
        codebook(),
        sleep=lambda _: None,
    )

    assert len(calls) == 1
    assert len(results) == 3
    assert results[0] == results[2]
    assert calls[0]["max_tokens"] == 400


@pytest.mark.integration
def test_bad_batch_shape_falls_back_to_single_coding() -> None:
    responses = [
        "not an array",
        '{"codes":[{"code":"Service","confidence":0.9}]}',
        '{"codes":[{"code":"Price","confidence":0.8}]}',
    ]

    def complete(**_: Any) -> str:
        return responses.pop(0)

    result = code_batch(
        complete,
        ["one", "two"],
        codebook(),
        sleep=lambda _: None,
    )
    assert [item["codes"][0]["code"] for item in result] == ["Service", "Price"]


@pytest.mark.integration
def test_apply_codes_adds_numeric_columns_and_audit_json() -> None:
    def complete(**_: Any) -> str:
        return json.dumps(
            [
                {"codes": [{"code": "Service", "confidence": "0.75"}]},
                {"codes": []},
            ]
        )

    dataframe = pd.DataFrame({"final_text_fr": ["great", "unclear"]})
    result = apply_codes_to_dataframe(
        complete,
        dataframe,
        codebook(),
        text_column="final_text_fr",
        coding_config=CodingConfig(coding_batch_size=2),
        sleep=lambda _: None,
    )

    assert result["code_Service"].tolist() == [1, 0]
    assert result["conf_Service"].tolist() == [0.75, 0.0]
    assert result["code_Other / Not classifiable"].tolist() == [0, 1]
    assert result["conf_Other / Not classifiable"].tolist() == [0.0, 0.5]
    coding_result = result.loc[1, "coding_result"]
    assert isinstance(coding_result, str)
    assert json.loads(coding_result)["fallback_reason"].startswith("Zero valid")
