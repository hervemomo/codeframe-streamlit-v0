"""Generated-codebook validation, retry, and traceability tests."""

import copy
import json
from datetime import UTC, datetime
from typing import Any

import pytest

from codeframe.codebook import (
    apply_cluster_traceability,
    ensure_other_code,
    extract_json,
    format_codebook_for_prompt_compact,
    generate_codebook,
    validate_codebook,
)
from codeframe.config import CodingConfig, LanguageConfig, ModelConfig


def entry(name: str, clusters: list[int]) -> dict[str, Any]:
    return {
        "name": name,
        "definition": f"Definition {name}",
        "inclusion_criteria": ["include"],
        "exclusion_criteria": ["exclude"],
        "example_verbatims": ["example"],
        "source_clusters": clusters,
    }


@pytest.mark.unit
def test_extract_json_is_fence_and_string_aware() -> None:
    assert extract_json('prose {"value":"} still text"} tail') == '{"value":"} still text"}'
    assert extract_json('```json\n[{"x": 1}]\n```') == '[{"x": 1}]'


@pytest.mark.unit
def test_validation_rejects_duplicate_names_and_partial_ids() -> None:
    duplicate = {"codes": [entry("A", [1]), entry("A", [2])]}
    with pytest.raises(ValueError, match="Duplicate code names"):
        validate_codebook(duplicate)

    partial_ids = {"codes": [entry("A", [1]) | {"code_id": "1"}, entry("B", [2])]}
    with pytest.raises(ValueError, match="missing code_id"):
        validate_codebook(partial_ids)


@pytest.mark.unit
def test_catch_all_does_not_invent_governed_id() -> None:
    codebook = {"codes": [entry("A", [1]) | {"code_id": "A1"}]}
    with pytest.raises(ValueError, match="Catch-all"):
        ensure_other_code(codebook, language_code="en")

    ensure_other_code(codebook, language_code="en", other_code_id="Z9")
    assert codebook["codes"][-1]["code_id"] == "Z9"


@pytest.mark.parity
def test_traceability_computes_counts_and_rejects_duplicate_claims() -> None:
    codebook = {
        "codes": [
            entry("Theme", [1, 2]),
            entry("Other / Not classifiable", []),
        ]
    }
    apply_cluster_traceability(
        codebook,
        cluster_sizes={0: 4, 1: 7},
        other_name="Other / Not classifiable",
        expected_clusters={1, 2},
    )
    assert codebook["codes"][0]["estimated_response_count"] == 11
    assert codebook["codes"][1]["estimated_response_count"] == 0

    duplicate = {"codes": [entry("A", [1]), entry("B", [1])]}
    with pytest.raises(ValueError, match="more than one code"):
        apply_cluster_traceability(
            duplicate,
            cluster_sizes={0: 2},
            other_name="Other / Not classifiable",
            expected_clusters={1},
        )


@pytest.mark.integration
def test_generate_codebook_retries_then_adds_metadata_and_traceability() -> None:
    valid = {
        "codes": [
            entry("Service", [1]),
            entry("Prix", [2]),
            entry("Autre / Non classifiable", []),
        ]
    }
    outputs = ['{"codes":[', json.dumps(valid, ensure_ascii=False)]
    calls: list[dict[str, Any]] = []

    def complete(**kwargs: Any) -> str:
        calls.append(kwargs)
        return outputs.pop(0)

    result = generate_codebook(
        complete,
        {0: ["bon service"], 1: ["trop cher"]},
        survey_context="Question",
        cluster_sizes={0: 3, 1: 4},
        language_config=LanguageConfig(codebook_language_code="fr"),
        model_config=ModelConfig(reasoning_model="mock-reasoner"),
        coding_config=CodingConfig(
            generation_max_tokens=100,
            generation_retry_max_tokens=200,
        ),
        now=lambda: datetime(2026, 1, 2, tzinfo=UTC),
    )

    assert [call["max_tokens"] for call in calls] == [100, 200]
    assert "IMPORTANT RETRY INSTRUCTION" in calls[1]["messages"][1]["content"]
    assert result["model"] == "mock-reasoner"
    assert result["generated_at"] == "2026-01-02T00:00:00+00:00"
    assert [code["estimated_response_count"] for code in result["codes"]] == [3, 4, 0]


@pytest.mark.unit
def test_compact_renderer_keeps_criteria_and_ids_but_omits_examples() -> None:
    codebook = {
        "codes": [entry("Theme", [1]) | {"code_id": "T1", "example_verbatims": ["secret verbatim"]}]
    }
    rendered = format_codebook_for_prompt_compact(copy.deepcopy(codebook))
    assert "[T1] Theme" in rendered
    assert "Include if: include" in rendered
    assert "Exclude if: exclude" in rendered
    assert "secret verbatim" not in rendered
