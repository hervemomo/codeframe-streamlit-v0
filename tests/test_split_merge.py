"""Split/merge deterministic transforms, confirmation, and stale-output tests."""

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from codeframe.merge_codes import (
    apply_confirmed_merges,
    merge_code_groups,
    merge_codes,
)
from codeframe.split_codes import apply_confirmed_splits, split_code


def entry(name: str, code_id: str) -> dict[str, Any]:
    return {
        "name": name,
        "code_id": code_id,
        "definition": f"Definition {name}",
        "inclusion_criteria": ["one", "two"],
        "exclusion_criteria": ["exclude"],
        "example_verbatims": ["example one", "example two"],
    }


def base_codebook() -> dict[str, Any]:
    return {
        "version": "v1",
        "multi_label": True,
        "codebook_language": "en",
        "codes": [
            entry("Parent", "P"),
            entry("Existing", "E"),
            entry("Other / Not classifiable", "O"),
        ],
    }


def split_dataframe() -> pd.DataFrame:
    results = [
        {"codes": [{"code": "Parent", "confidence": 0.8}, {"code": "Existing", "confidence": 0.6}]},
        {"codes": [{"code": "Parent", "confidence": 0.7}]},
        {"codes": [{"code": "Existing", "confidence": 0.9}]},
    ]
    return pd.DataFrame(
        {
            "response_id": ["R1", "R2", "R3"],
            "original_text": ["one", "two", "three"],
            "final_text_fr": ["one", "two", "three"],
            "is_valid": [True, True, True],
            "code_Parent": [1, 1, 0],
            "conf_Parent": [0.8, 0.7, 0.0],
            "code_Existing": [1, 0, 1],
            "conf_Existing": [0.6, 0.0, 0.9],
            "code_Other / Not classifiable": [0, 0, 0],
            "conf_Other / Not classifiable": [0.0, 0.0, 0.0],
            "coding_result": [json.dumps(result) for result in results],
            "coding_status": ["coded", "coded", "coded"],
        }
    )


@pytest.mark.parity
def test_split_recodes_only_affected_rows_and_replaces_parent(tmp_path: Path) -> None:
    calls = 0

    def complete(**_: Any) -> str:
        nonlocal calls
        calls += 1
        return json.dumps(
            [
                {"codes": [{"code": "Sub A", "confidence": 0.9}]},
                {"codes": [{"code": "Sub B", "confidence": 0.8}]},
            ]
        )

    result, codebook, outputs = split_code(
        split_dataframe(),
        base_codebook(),
        complete,
        "Parent",
        subcodes=["Sub A", "Sub B"],
        subcode_definitions=["Definition A", "Definition B"],
        enrich_subcodes=False,
        text_column="final_text_fr",
        output_dir=tmp_path,
        output_file="split.xlsx",
        include_charts=False,
        sleep=lambda _: None,
    )

    assert calls == 1
    assert "code_Parent" not in result.columns
    assert result["code_Sub A"].tolist() == [1, 0, 0]
    assert result["code_Sub B"].tolist() == [0, 1, 0]
    assert result["code_Existing"].tolist() == [1, 0, 1]
    assert [code["name"] for code in codebook["codes"]] == [
        "Sub A",
        "Sub B",
        "Existing",
        "Other / Not classifiable",
    ]
    assert [code["code_id"] for code in codebook["codes"][:2]] == [
        "P_SUB_A",
        "P_SUB_B",
    ]
    summary_report = outputs["summary_report"]
    assert summary_report is not None
    assert Path(summary_report).is_file()


@pytest.mark.parity
def test_split_no_match_routes_to_main_catchall(tmp_path: Path) -> None:
    def complete(**_: Any) -> str:
        return json.dumps([{"codes": []}, {"codes": []}])

    result, _, _ = split_code(
        split_dataframe(),
        base_codebook(),
        complete,
        "Parent",
        subcodes=["Sub A", "Sub B"],
        subcode_definitions=["Definition A", "Definition B"],
        enrich_subcodes=False,
        text_column="final_text_fr",
        output_dir=tmp_path,
        include_charts=False,
        sleep=lambda _: None,
    )

    assert result["code_Other / Not classifiable"].tolist() == [0, 1, 0]
    assert result["code_Existing"].tolist() == [1, 0, 1]


@pytest.mark.integration
def test_split_ai_enrichment_populates_all_operational_fields(tmp_path: Path) -> None:
    responses = [
        json.dumps(
            {
                "codes": [
                    {
                        "name": "Sub A",
                        "definition": "Definition A",
                        "inclusion_criteria": ["a1", "a2"],
                        "exclusion_criteria": ["not a"],
                        "example_verbatims": ["a example", "a sample"],
                    },
                    {
                        "name": "Sub B",
                        "definition": "Definition B",
                        "inclusion_criteria": ["b1", "b2"],
                        "exclusion_criteria": ["not b"],
                        "example_verbatims": ["b example", "b sample"],
                    },
                ]
            }
        ),
        json.dumps(
            [
                {"codes": [{"code": "Sub A", "confidence": 0.9}]},
                {"codes": [{"code": "Sub B", "confidence": 0.8}]},
            ]
        ),
    ]
    prompts: list[str] = []

    def complete(**kwargs: Any) -> str:
        prompts.append(kwargs["messages"][1]["content"])
        return responses.pop(0)

    _, codebook, _ = split_code(
        split_dataframe(),
        base_codebook(),
        complete,
        "Parent",
        subcodes=["Sub A", "Sub B"],
        enrich_subcodes=True,
        text_column="final_text_fr",
        output_dir=tmp_path,
        include_charts=False,
        sleep=lambda _: None,
    )

    assert codebook["codes"][0]["inclusion_criteria"] == ["a1", "a2"]
    assert codebook["codes"][1]["example_verbatims"] == ["b example", "b sample"]
    assert "missing_fields" in prompts[0]


@pytest.mark.integration
def test_split_ai_proposes_subcode_names_when_none_supplied(tmp_path: Path) -> None:
    responses = [
        json.dumps({"subcodes": ["Sub A", "Sub B"]}),
        json.dumps(
            {
                "codes": [
                    {
                        "name": "Sub A",
                        "definition": "Definition A",
                        "inclusion_criteria": ["a1", "a2"],
                        "exclusion_criteria": ["not a"],
                        "example_verbatims": ["a example", "a sample"],
                    },
                    {
                        "name": "Sub B",
                        "definition": "Definition B",
                        "inclusion_criteria": ["b1", "b2"],
                        "exclusion_criteria": ["not b"],
                        "example_verbatims": ["b example", "b sample"],
                    },
                ]
            }
        ),
        json.dumps(
            [
                {"codes": [{"code": "Sub A", "confidence": 0.9}]},
                {"codes": [{"code": "Sub B", "confidence": 0.8}]},
            ]
        ),
    ]
    prompts: list[str] = []

    def complete(**kwargs: Any) -> str:
        prompts.append(kwargs["messages"][1]["content"])
        return responses.pop(0)

    result, codebook, _ = split_code(
        split_dataframe(),
        base_codebook(),
        complete,
        "Parent",
        n_subcodes_proposed=2,
        enrich_subcodes=True,
        text_column="final_text_fr",
        output_dir=tmp_path,
        include_charts=False,
        sleep=lambda _: None,
    )

    assert [code["name"] for code in codebook["codes"][:2]] == ["Sub A", "Sub B"]
    assert result["code_Sub A"].tolist() == [1, 0, 0]
    assert result["code_Sub B"].tolist() == [0, 1, 0]
    assert "too broad" in prompts[0]
    assert "EXISTING CODE NAMES" in prompts[0]


@pytest.mark.unit
def test_split_proposal_with_malformed_json_raises(tmp_path: Path) -> None:
    def complete(**_: Any) -> str:
        return "not valid json"

    with pytest.raises(ValueError, match="Model returned no sub-codes."):
        split_code(
            split_dataframe(),
            base_codebook(),
            complete,
            "Parent",
            text_column="final_text_fr",
            output_dir=tmp_path,
            include_charts=False,
            sleep=lambda _: None,
        )


@pytest.mark.unit
def test_cancelled_split_returns_fresh_unchanged_state(tmp_path: Path) -> None:
    dataframe = split_dataframe()
    codebook = base_codebook()
    result = apply_confirmed_splits(
        dataframe,
        codebook,
        lambda **_: "",
        [{"parent_code": "Parent"}],
        confirmed=False,
        output_dir=tmp_path,
    )
    assert result.did_run is False
    assert result.outputs == []
    assert result.dataframe.equals(dataframe)
    assert result.dataframe is not dataframe
    assert result.codebook == codebook
    assert result.codebook is not codebook


def merge_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "response_id": ["R1", "R2", "R3", "R4"],
            "original_text": ["one", "two", "three", "four"],
            "final_text_fr": ["one", "two", "three", "four"],
            "is_valid": [True] * 4,
            "code_A": [1, 0, 1, 0],
            "conf_A": [0.8, 0.0, 0.5, 0.0],
            "code_B": [0, 1, 1, 0],
            "conf_B": [0.0, 0.7, 0.9, 0.0],
            "code_C": [0, 0, 1, 1],
            "conf_C": [0.0, 0.0, 0.6, 0.8],
        }
    )


def merge_codebook() -> dict[str, Any]:
    return {
        "version": "v1",
        "multi_label": True,
        "codebook_language": "en",
        "codes": [
            entry("A", "A"),
            entry("B", "B"),
            entry("C", "C"),
        ],
    }


@pytest.mark.parity
def test_merge_is_deterministic_or_and_max_without_llm_reclassification(
    tmp_path: Path,
) -> None:
    def no_call(**_: Any) -> str:
        raise AssertionError("LLM must not be called for a complete manual merge")

    result, codebook, outputs = merge_codes(
        merge_dataframe(),
        merge_codebook(),
        no_call,
        ["A", "B"],
        merged_name="AB",
        merged_definition="Combined",
        merged_inclusion_criteria=["one"],
        merged_exclusion_criteria=["exclude"],
        merged_example_verbatims=["x", "y"],
        enrich_merged=False,
        text_column="final_text_fr",
        output_dir=tmp_path,
        output_file="merge.xlsx",
        include_charts=False,
    )

    assert result["code_AB"].tolist() == [1, 1, 1, 0]
    assert result["conf_AB"].tolist() == [0.8, 0.7, 0.9, 0.0]
    assert "code_A" not in result.columns
    assert "code_B" not in result.columns
    assert result["code_C"].tolist() == [0, 0, 1, 1]
    assert [code["name"] for code in codebook["codes"]] == ["AB", "C"]
    assert codebook["codes"][0]["code_id"] == "MERGE_AB"
    assert codebook["codes"][0]["merged_from"] == ["A", "B"]
    summary_report = outputs["summary_report"]
    assert summary_report is not None
    assert Path(summary_report).is_file()


@pytest.mark.integration
def test_merge_ai_name_and_enrichment_are_grounded_in_sources(tmp_path: Path) -> None:
    outputs = [
        '{"name":"Combined Theme","definition":"Combined definition"}',
        json.dumps(
            {
                "codes": [
                    {
                        "name": "Combined Theme",
                        "inclusion_criteria": ["one", "two"],
                        "exclusion_criteria": ["exclude"],
                        "example_verbatims": ["example one", "example two"],
                    }
                ]
            }
        ),
    ]
    prompts: list[str] = []

    def complete(**kwargs: Any) -> str:
        prompts.append(kwargs["messages"][1]["content"])
        return outputs.pop(0)

    result, codebook, _ = merge_codes(
        merge_dataframe(),
        merge_codebook(),
        complete,
        ["A", "B"],
        enrich_merged=True,
        text_column="final_text_fr",
        output_dir=tmp_path,
        include_charts=False,
    )

    assert result["code_Combined Theme"].tolist() == [1, 1, 1, 0]
    assert codebook["codes"][0]["definition"] == "Combined definition"
    assert codebook["codes"][0]["inclusion_criteria"] == ["one", "two"]
    assert "SELECTED SOURCE CODES" in prompts[0]
    assert "REPRESENTATIVE ASSIGNED RESPONSES" in prompts[1]


@pytest.mark.unit
def test_merge_name_proposal_with_malformed_json_raises(tmp_path: Path) -> None:
    def complete(**_: Any) -> str:
        return "not valid json"

    with pytest.raises(ValueError, match="Model returned no name."):
        merge_codes(
            merge_dataframe(),
            merge_codebook(),
            complete,
            ["A", "B"],
            enrich_merged=False,
            text_column="final_text_fr",
            output_dir=tmp_path,
            include_charts=False,
        )


@pytest.mark.unit
def test_merge_groups_rejects_reused_sources(tmp_path: Path) -> None:
    configs = [
        {
            "codes_to_merge": ["A", "B"],
            "merged_name": "AB",
            "merged_definition": "d",
            "merged_inclusion_criteria": ["i"],
            "merged_exclusion_criteria": ["e"],
            "merged_example_verbatims": ["x", "y"],
            "enrich": False,
        },
        {
            "codes_to_merge": ["B", "C"],
            "merged_name": "BC",
            "merged_definition": "d",
            "merged_inclusion_criteria": ["i"],
            "merged_exclusion_criteria": ["e"],
            "merged_example_verbatims": ["x", "y"],
            "enrich": False,
        },
    ]
    with pytest.raises(ValueError, match="reuses source"):
        merge_code_groups(
            merge_dataframe(),
            merge_codebook(),
            lambda **_: "",
            configs,
            text_column="final_text_fr",
            output_dir=tmp_path,
            include_charts=False,
        )


@pytest.mark.unit
def test_cancelled_merge_has_no_stale_outputs(tmp_path: Path) -> None:
    dataframe = merge_dataframe()
    codebook = merge_codebook()
    result = apply_confirmed_merges(
        dataframe,
        codebook,
        lambda **_: "",
        [{"codes_to_merge": ["A", "B"]}],
        confirmed=False,
        output_dir=tmp_path,
    )
    assert result.did_run is False
    assert result.outputs == []
    assert result.dataframe.equals(dataframe)
    assert result.codebook == codebook


@pytest.mark.unit
def test_confirmation_with_empty_plan_fails_fast(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="split_configs is empty"):
        apply_confirmed_splits(
            split_dataframe(),
            base_codebook(),
            lambda **_: "",
            [],
            confirmed=True,
            output_dir=tmp_path,
        )
    with pytest.raises(ValueError, match="merge_configs is empty"):
        apply_confirmed_merges(
            merge_dataframe(),
            merge_codebook(),
            lambda **_: "",
            [],
            confirmed=True,
            output_dir=tmp_path,
        )
