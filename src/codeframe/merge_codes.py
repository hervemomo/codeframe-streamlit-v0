"""Explicitly confirmed deterministic code-merging workflow."""

import copy
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from codeframe.codebook import (
    CODE_ID_FIELD,
    CodebookMapping,
    add_codes_column,
    auto_code_id_for_new_code,
    canonical_code_key,
    clean_code_id,
    existing_code_ids,
    extract_json,
    make_code_entry,
    same_code_name_set,
    validate_codebook,
)
from codeframe.config import ModelConfig
from codeframe.llm_client import TextCompletion
from codeframe.reporting import generate_reports
from codeframe.split_codes import (
    _apply_definition_fallbacks,
    enrich_derived_codebook,
)


def _normalize_string_list(value: object, label: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list | tuple):
        raise TypeError(f"{label} must be a list of strings.")
    cleaned = [item.strip() for item in value if isinstance(item, str) and item.strip()]
    if len(cleaned) != len(value):
        raise ValueError(f"{label} contains a blank or non-string item.")
    return cleaned


def merge_codes(
    dataframe: pd.DataFrame,
    codebook: CodebookMapping,
    complete: TextCompletion,
    codes_to_merge: Sequence[str],
    *,
    merged_name: str = "",
    merged_code_id: object = "",
    merged_definition: object = "",
    merged_inclusion_criteria: Sequence[str] | None = None,
    merged_exclusion_criteria: Sequence[str] | None = None,
    merged_example_verbatims: Sequence[str] | None = None,
    enrich_merged: bool = True,
    survey_context: str = "",
    text_column: str = "final_text_fr",
    output_dir: Path,
    output_file: str = "merge.xlsx",
    model_config: ModelConfig | None = None,
    include_charts: bool = True,
) -> tuple[pd.DataFrame, CodebookMapping, dict[str, str | None]]:
    """Merge two or more codes using deterministic OR/max assignments."""

    models = model_config or ModelConfig()
    sources = list(codes_to_merge)
    if len(sources) < 2:
        raise ValueError("Need ≥ 2 codes to merge.")
    code_names = [str(code["name"]) for code in codebook["codes"]]
    missing = [name for name in sources if name not in code_names]
    if missing:
        raise ValueError(f"Not in codebook: {missing}. Available: {code_names}")
    source_entries = [code for code in codebook["codes"] if code["name"] in sources]
    source_context = [
        {
            "code_id": clean_code_id(code.get(CODE_ID_FIELD, "")),
            "name": code["name"],
            "definition": code.get("definition", ""),
            "inclusion_criteria": copy.deepcopy(code.get("inclusion_criteria", [])),
            "exclusion_criteria": copy.deepcopy(code.get("exclusion_criteria", [])),
            "example_verbatims": copy.deepcopy(code.get("example_verbatims", [])),
        }
        for code in source_entries
    ]
    source_columns = [f"code_{name}" for name in sources]
    confidence_columns = [f"conf_{name}" for name in sources]
    missing_columns = [column for column in source_columns if column not in dataframe.columns]
    if missing_columns:
        raise KeyError(f"Columns not found: {missing_columns}. Run coding first.")
    if text_column not in dataframe.columns:
        raise KeyError(f"Text column not found for merge evidence: {text_column}")
    affected = dataframe[source_columns].fillna(0).max(axis=1) > 0
    samples: list[str] = []
    for value in dataframe.loc[affected, text_column].tolist():
        text = str(value).strip()
        if text and text not in samples:
            samples.append(text)
        if len(samples) >= 30:
            break

    identifier = clean_code_id(merged_code_id)
    definition = "" if merged_definition is None else str(merged_definition).strip()
    inclusion = _normalize_string_list(
        merged_inclusion_criteria,
        "merged_inclusion_criteria",
    )
    exclusion = _normalize_string_list(
        merged_exclusion_criteria,
        "merged_exclusion_criteria",
    )
    examples = _normalize_string_list(
        merged_example_verbatims,
        "merged_example_verbatims",
    )
    final_name = merged_name.strip()
    if not final_name:
        language = "English" if codebook.get("codebook_language") == "en" else "French"
        source_json = json.dumps(source_context, ensure_ascii=False, indent=2)
        samples_json = json.dumps(samples, ensure_ascii=False, indent=2)
        prompt = (
            "You are a qualitative research expert.\n\n"
            f"CODEBOOK OUTPUT LANGUAGE: {language}.\n"
            f"Generate the merged code name and definition in {language}.\n\n"
            f"CONTEXT: {survey_context}\n\n"
            "Use the complete selected-code records and assigned-response samples "
            "below as evidence.\n"
            f"SELECTED SOURCE CODES:\n{source_json}\n\n"
            f"REPRESENTATIVE ASSIGNED RESPONSES:\n{samples_json}\n\n"
            f"Propose a short name (max 5 words) and a 1-2 sentence definition in {language}.\n"
            "The merged concept must cover the union of the selected codes without "
            "inventing an unrelated theme.\nReturn ONLY valid JSON:\n"
            '{"name": "...", "definition": "..."}'
        )
        content = complete(
            model=models.reasoning_model,
            messages=[
                {
                    "role": "system",
                    "content": "Qualitative coding expert. Return ONLY valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=models.reasoning_temperature,
            seed=models.reasoning_seed,
            max_tokens=300,
        )
        try:
            parsed = json.loads(extract_json(content))
            final_name = str(parsed.get("name", "")).strip()
            proposed_definition = str(parsed.get("definition", "")).strip()
            if not definition:
                definition = proposed_definition
        except (json.JSONDecodeError, TypeError, ValueError, AttributeError):
            final_name = ""
        if not final_name:
            raise ValueError("Model returned no name.")

    existing_target_keys = {
        canonical_code_key(code["name"])
        for code in codebook["codes"]
        if code["name"] not in sources
    }
    if canonical_code_key(final_name) in existing_target_keys:
        raise ValueError(
            f'Merged code name "{final_name}" already exists outside the source group.'
        )

    requires_ids = any(clean_code_id(code.get(CODE_ID_FIELD, "")) for code in codebook["codes"])
    merged_from_ids = [
        clean_code_id(code.get(CODE_ID_FIELD, ""))
        for code in source_entries
        if clean_code_id(code.get(CODE_ID_FIELD, ""))
    ]
    if requires_ids:
        reserved = existing_code_ids(codebook)
        if identifier:
            if identifier in reserved:
                raise ValueError(f"merged_code_id already exists in the codebook: {identifier}")
        else:
            identifier = auto_code_id_for_new_code(
                codebook,
                final_name,
                prefix="MERGE",
                existing_ids=reserved,
            )
    else:
        identifier = ""

    missing_fields: list[str] = []
    if not definition:
        missing_fields.append("definition")
    if not inclusion:
        missing_fields.append("inclusion_criteria")
    if not exclusion:
        missing_fields.append("exclusion_criteria")
    if not examples:
        missing_fields.append("example_verbatims")
    if missing_fields and not enrich_merged:
        raise ValueError(
            "Merge-derived code is missing required operational fields: "
            f"{missing_fields}. Provide them manually or set enrich=True."
        )
    merged_entry = make_code_entry(
        final_name,
        code_id=identifier,
        definition=definition,
        inclusion_criteria=inclusion,
        exclusion_criteria=exclusion,
        example_verbatims=examples,
        merged_from=sources,
        merged_from_ids=merged_from_ids,
        source="manual_merge" if merged_name.strip() else "ai_merge_proposal",
    )
    if enrich_merged:
        mini: CodebookMapping = {
            "codes": [merged_entry],
            "multi_label": codebook.get("multi_label", True),
            "codebook_language": codebook.get("codebook_language", "fr"),
        }
        enrich_derived_codebook(
            complete,
            mini,
            survey_context=survey_context,
            model_config=models,
            fallback_merged_from=sources,
            source_code_context=source_context,
            response_samples=samples,
        )
        merged_entry = mini["codes"][0]
    if not str(merged_entry.get("definition", "")).strip():
        mini = {
            "codes": [merged_entry],
            "multi_label": codebook.get("multi_label", True),
            "codebook_language": codebook.get("codebook_language", "fr"),
        }
        _apply_definition_fallbacks(
            mini,
            survey_context=survey_context,
            merged_from=sources,
            reason="deterministic_fallback_after_ai_enrichment",
        )
        merged_entry = mini["codes"][0]

    working = dataframe.copy(deep=True)
    working[f"code_{final_name}"] = working[source_columns].max(axis=1).astype(int)
    available_confidence = [column for column in confidence_columns if column in working.columns]
    working[f"conf_{final_name}"] = (
        working[available_confidence].max(axis=1)
        if available_confidence
        else working[f"code_{final_name}"].astype(float)
    )
    working.drop(
        columns=[
            column for column in source_columns + confidence_columns if column in working.columns
        ],
        inplace=True,
    )
    updated_codes: list[dict[str, Any]] = []
    inserted = False
    for code in codebook["codes"]:
        if code["name"] in sources:
            if not inserted:
                updated_codes.append(merged_entry)
                inserted = True
        else:
            updated_codes.append(copy.deepcopy(code))
    updated_codebook: CodebookMapping = {
        **copy.deepcopy(codebook),
        "codes": updated_codes,
        "version": f"{codebook.get('version', '1.0')}+merge",
    }
    validate_codebook(updated_codebook)
    add_codes_column(working, updated_codebook)
    outputs = generate_reports(
        working,
        updated_codebook,
        output_dir=output_dir,
        file_stem=Path(output_file).stem,
        text_column=text_column,
        output_file=output_file,
        include_charts=include_charts,
    )
    return working, updated_codebook, outputs


def merge_code_groups(
    dataframe: pd.DataFrame,
    codebook: CodebookMapping,
    complete: TextCompletion,
    merge_configs: Sequence[dict[str, Any]],
    *,
    survey_context: str = "",
    text_column: str = "final_text_fr",
    output_dir: Path,
    output_file: str = "merge.xlsx",
    model_config: ModelConfig | None = None,
    include_charts: bool = True,
) -> tuple[pd.DataFrame, CodebookMapping, list[dict[str, str | None]]]:
    """Apply one or more non-overlapping merge groups sequentially."""

    if not merge_configs:
        raise ValueError("merge_configs is empty. Add at least one merge group.")
    working = dataframe.copy(deep=True)
    working_codebook = copy.deepcopy(codebook)
    outputs: list[dict[str, str | None]] = []
    used_sources: set[str] = set()
    target_keys: set[str] = set()
    for position, config in enumerate(merge_configs, 1):
        if not isinstance(config, dict):
            raise TypeError(f"Merge config #{position} must be a dict.")
        sources = config.get("codes_to_merge", [])
        if isinstance(sources, str):
            raise TypeError(
                f"Merge config #{position} codes_to_merge must be a list, not a string."
            )
        if not isinstance(sources, Sequence) or len(sources) < 2:
            raise ValueError(f"Merge config #{position} needs at least 2 source codes.")
        source_names = [str(name) for name in sources]
        duplicates = [name for name in source_names if name in used_sources]
        if duplicates:
            raise ValueError(f"Merge config #{position} reuses source code(s): {duplicates}.")
        target_name = str(config.get("merged_name", "") or "").strip()
        if target_name and canonical_code_key(target_name) in target_keys:
            raise ValueError(f"Merge config #{position} uses duplicate merged_name: {target_name}")
        if target_name:
            target_keys.add(canonical_code_key(target_name))
        group_file = output_file
        if len(merge_configs) > 1:
            path = Path(output_file)
            group_file = f"{path.stem}_group_{position}{path.suffix}"
        working, working_codebook, group_outputs = merge_codes(
            working,
            working_codebook,
            complete,
            source_names,
            merged_name=target_name,
            merged_code_id=config.get("merged_code_id", ""),
            merged_definition=config.get("merged_definition", ""),
            merged_inclusion_criteria=config.get("merged_inclusion_criteria", []),
            merged_exclusion_criteria=config.get("merged_exclusion_criteria", []),
            merged_example_verbatims=config.get("merged_example_verbatims", []),
            enrich_merged=bool(config.get("enrich", True)),
            survey_context=survey_context,
            text_column=text_column,
            output_dir=output_dir,
            output_file=group_file,
            model_config=model_config,
            include_charts=include_charts,
        )
        outputs.append(group_outputs)
        used_sources.update(source_names)
        if not target_name:
            created = [
                str(code["name"])
                for code in working_codebook["codes"]
                if same_code_name_set(code.get("merged_from", []), source_names)
            ]
            if created:
                target_keys.add(canonical_code_key(created[0]))
    return working, working_codebook, outputs


@dataclass(frozen=True, slots=True)
class MergeRunResult:
    dataframe: pd.DataFrame
    codebook: CodebookMapping
    outputs: list[dict[str, str | None]]
    did_run: bool


def apply_confirmed_merges(
    dataframe: pd.DataFrame,
    codebook: CodebookMapping,
    complete: TextCompletion,
    merge_configs: Sequence[dict[str, Any]],
    *,
    confirmed: bool,
    **kwargs: Any,
) -> MergeRunResult:
    """Apply only an explicitly confirmed plan and prevent stale output reuse."""

    if confirmed and not merge_configs:
        raise ValueError("confirmed=True but merge_configs is empty.")
    if not confirmed or not merge_configs:
        return MergeRunResult(
            dataframe.copy(deep=True),
            copy.deepcopy(codebook),
            [],
            False,
        )
    result = merge_code_groups(
        dataframe,
        codebook,
        complete,
        merge_configs,
        **kwargs,
    )
    return MergeRunResult(*result, True)
