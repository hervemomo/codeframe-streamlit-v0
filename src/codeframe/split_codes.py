"""Explicitly confirmed code-splitting workflow."""

import copy
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from codeframe.ai_coding import code_batch, normalize_coding_result
from codeframe.codebook import (
    CODE_ID_FIELD,
    CodebookMapping,
    add_codes_column,
    auto_code_id_for_new_code,
    clean_code_id,
    existing_code_ids,
    extract_json,
    get_other_code_name,
    make_code_entry,
    normalize_manual_id_list,
    safe_confidence,
    slugify_for_code_id,
    validate_codebook,
)
from codeframe.config import CodingConfig, ModelConfig
from codeframe.llm_client import TextCompletion
from codeframe.reporting import generate_reports


def _language_name(codebook: CodebookMapping) -> str:
    return "English" if codebook.get("codebook_language") == "en" else "French"


def _missing_operational_fields(code: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if not str(code.get("definition", "")).strip():
        missing.append("definition")
    for field in ("inclusion_criteria", "exclusion_criteria", "example_verbatims"):
        if not code.get(field):
            missing.append(field)
    return missing


def _fallback_definition(
    name: str,
    *,
    context: str,
    parent_code: str = "",
    merged_from: Sequence[str] | None = None,
    language_code: str = "fr",
) -> str:
    if language_code == "en":
        if merged_from:
            base = (
                f'Responses grouped under "{name}", consolidating ideas previously '
                f"coded as: {', '.join(merged_from)}."
            )
        elif parent_code:
            base = (
                f'Responses related to the sub-theme "{name}" within the parent '
                f'code "{parent_code}".'
            )
        else:
            base = f'Responses associated with the theme "{name}".'
        return base + (
            " Use when the verbatim clearly matches this theme in the study context."
            if context.strip()
            else " Use when the verbatim clearly matches this theme."
        )
    if merged_from:
        base = (
            f"Réponses regroupées sous « {name} », consolidant les idées auparavant "
            f"codées comme : {', '.join(merged_from)}."
        )
    elif parent_code:
        base = f"Réponses relevant du sous-thème « {name} » dans le code parent « {parent_code} »."
    else:
        base = f"Réponses associées au thème « {name} »."
    return base + (
        " À utiliser lorsque le verbatim correspond clairement à ce thème "
        "dans le contexte de l’étude."
        if context.strip()
        else " À utiliser lorsque le verbatim correspond clairement à ce thème."
    )


def _apply_definition_fallbacks(
    codebook: CodebookMapping,
    *,
    survey_context: str,
    parent_code: str = "",
    merged_from: Sequence[str] | None = None,
    reason: str,
) -> CodebookMapping:
    language = str(codebook.get("codebook_language", "fr"))
    for code in codebook["codes"]:
        if str(code.get("definition", "")).strip():
            continue
        code["definition"] = _fallback_definition(
            str(code.get("name", "")),
            context=survey_context,
            parent_code=parent_code,
            merged_from=merged_from,
            language_code=language,
        )
        code["definition_source"] = reason
        if not code.get("inclusion_criteria"):
            code["inclusion_criteria"] = (
                [
                    f'The verbatim clearly matches the theme "{code["name"]}".',
                    "The main meaning of the response is consistent with this category.",
                ]
                if language == "en"
                else [
                    f"Le verbatim correspond clairement au thème « {code['name']} ».",
                    "Le sens principal de la réponse est cohérent avec cette catégorie.",
                ]
            )
        if not code.get("exclusion_criteria"):
            code["exclusion_criteria"] = (
                [
                    "Do not use if a more specific or more appropriate code applies.",
                    "Do not use if the verbatim is ambiguous or not clearly related to this theme.",
                ]
                if language == "en"
                else [
                    "Ne pas utiliser si un code plus spécifique ou plus approprié s’applique.",
                    "Ne pas utiliser si le verbatim est ambigu ou sans lien clair avec ce thème.",
                ]
            )
    return codebook


def enrich_derived_codebook(
    complete: TextCompletion,
    codebook: CodebookMapping,
    *,
    survey_context: str,
    model_config: ModelConfig | None = None,
    fallback_parent_code: str = "",
    fallback_merged_from: Sequence[str] | None = None,
    source_code_context: Sequence[dict[str, Any]] | None = None,
    response_samples: Sequence[str] | None = None,
) -> CodebookMapping:
    """Fill missing split/merge operational fields, preserving supplied values."""

    models = model_config or ModelConfig()
    to_enrich = [code for code in codebook["codes"] if _missing_operational_fields(code)]
    if not to_enrich:
        return codebook
    requests: list[dict[str, Any]] = []
    for code in to_enrich:
        request = {
            "name": code["name"],
            "missing_fields": _missing_operational_fields(code),
            "existing_fields_read_only": {
                field: copy.deepcopy(code.get(field))
                for field in (
                    "definition",
                    "inclusion_criteria",
                    "exclusion_criteria",
                    "example_verbatims",
                )
            },
        }
        identifier = clean_code_id(code.get(CODE_ID_FIELD, ""))
        if identifier:
            request["code_id"] = identifier
        requests.append(request)
    evidence: list[str] = []
    if source_code_context:
        evidence.append(
            "SELECTED SOURCE CODES (authoritative merge evidence):\n"
            + json.dumps(source_code_context, ensure_ascii=False, indent=2)
        )
    if response_samples:
        evidence.append(
            "REPRESENTATIVE ASSIGNED RESPONSES:\n"
            + json.dumps(list(response_samples)[:30], ensure_ascii=False, indent=2)
        )
    language = _language_name(codebook)
    prompt = (
        "You are a qualitative research expert.\n\n"
        f"CODEBOOK OUTPUT LANGUAGE: {language}.\n"
        f"Write all generated definitions, criteria, and example verbatims in {language}.\n\n"
        f"CONTEXT:\n{survey_context or 'Open-ended survey responses.'}\n\n"
        + (("\n\n".join(evidence) + "\n\n") if evidence else "")
        + f"CODE ENTRIES:\n{json.dumps(requests, ensure_ascii=False, indent=2)}\n\n"
        f"For each code, generate only its listed missing_fields in {language}:\n"
        "- definition: a clear operational definition (1-2 sentences)\n"
        "- inclusion_criteria: 2-3 practical criteria\n"
        "- exclusion_criteria: 1-2 practical criteria\n"
        "- example_verbatims: 2-3 realistic sample responses\n\n"
        "Return ONLY valid JSON, with no Markdown:\n"
        '{"codes":[{"name":"<exact name>","definition":"...",'
        '"inclusion_criteria":["..."],"exclusion_criteria":["..."],'
        '"example_verbatims":["...","..."]}]}'
    )
    try:
        content = complete(
            model=models.coding_model,
            messages=[
                {
                    "role": "system",
                    "content": "Qualitative research expert. Return ONLY valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=8000,
        )
        parsed = json.loads(extract_json(content.strip()))
        returned = parsed.get("codes", []) if isinstance(parsed, dict) else []
    except (json.JSONDecodeError, TypeError, ValueError):
        returned = []
    by_name = {
        str(item.get("name", "")).casefold(): item for item in returned if isinstance(item, dict)
    }
    by_id = {
        clean_code_id(item.get(CODE_ID_FIELD, "")): item
        for item in returned
        if isinstance(item, dict) and clean_code_id(item.get(CODE_ID_FIELD, ""))
    }
    limits = {
        "inclusion_criteria": (2, 3),
        "exclusion_criteria": (1, 2),
        "example_verbatims": (2, 3),
    }
    for code in to_enrich:
        missing = _missing_operational_fields(code)
        identifier = clean_code_id(code.get(CODE_ID_FIELD, ""))
        patch = by_id.get(identifier) if identifier else None
        if patch is None:
            patch = by_name.get(str(code["name"]).casefold())
        if not patch:
            continue
        populated: list[str] = []
        if "definition" in missing:
            definition = str(patch.get("definition", "")).strip()
            if definition:
                code["definition"] = definition
                code["definition_source"] = "ai_enrichment"
                populated.append("definition")
        for field, (minimum, maximum) in limits.items():
            value = patch.get(field, [])
            cleaned = (
                [item.strip() for item in value if isinstance(item, str) and item.strip()]
                if isinstance(value, list)
                else []
            )
            if field in missing and minimum <= len(cleaned) <= maximum:
                code[field] = cleaned
                populated.append(field)
        if populated:
            code["ai_enriched_fields"] = sorted(set(code.get("ai_enriched_fields", []) + populated))
    if any(_missing_operational_fields(code) for code in codebook["codes"]):
        _apply_definition_fallbacks(
            codebook,
            survey_context=survey_context,
            parent_code=fallback_parent_code,
            merged_from=fallback_merged_from,
            reason="deterministic_fallback_after_ai_enrichment",
        )
    incomplete = {
        str(code["name"]): _missing_operational_fields(code)
        for code in codebook["codes"]
        if _missing_operational_fields(code)
    }
    if incomplete:
        raise ValueError(
            "AI enrichment did not return every required split/merge field: "
            f"{incomplete}. Retry enrichment before reassigning responses."
        )
    return codebook


def _previous_entries(
    dataframe: pd.DataFrame,
    index: object,
    codebook: CodebookMapping,
) -> list[dict[str, Any]]:
    if "coding_result" in dataframe.columns:
        try:
            result = json.loads(str(dataframe.at[index, "coding_result"]))
            if isinstance(result, dict) and isinstance(result.get("codes"), list):
                return copy.deepcopy(result["codes"])
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    entries: list[dict[str, Any]] = []
    for code in codebook["codes"]:
        name = str(code["name"])
        if f"code_{name}" in dataframe.columns and dataframe.at[index, f"code_{name}"] == 1:
            entry: dict[str, Any] = {"code": name}
            confidence_column = f"conf_{name}"
            if confidence_column in dataframe.columns and pd.notna(
                dataframe.at[index, confidence_column]
            ):
                entry["confidence"] = dataframe.at[index, confidence_column]
            entries.append(entry)
    return entries


def _combine_split_entries(
    previous: Sequence[object],
    split_entries: Sequence[object],
    parent_code: str,
    *,
    preserve_parent: bool,
) -> list[object]:
    combined: list[object] = []
    replaced = False
    for entry in previous:
        name = entry.get("code") if isinstance(entry, dict) else entry
        if name == parent_code:
            if preserve_parent:
                combined.append(copy.deepcopy(entry))
            combined.extend(copy.deepcopy(list(split_entries)))
            replaced = True
        else:
            combined.append(copy.deepcopy(entry))
    if not replaced:
        combined.extend(copy.deepcopy(list(split_entries)))
    return combined


def split_code(
    dataframe: pd.DataFrame,
    codebook: CodebookMapping,
    complete: TextCompletion,
    parent_code: str,
    *,
    subcodes: Sequence[str] | None = None,
    subcode_ids: Sequence[object] | None = None,
    subcode_definitions: Sequence[object] | None = None,
    n_subcodes_proposed: int = 3,
    enrich_subcodes: bool = True,
    survey_context: str = "",
    text_column: str = "final_text_fr",
    output_dir: Path,
    output_file: str = "split.xlsx",
    preserve_parent: bool = False,
    model_config: ModelConfig | None = None,
    coding_config: CodingConfig | None = None,
    include_charts: bool = True,
    sleep: Callable[[float], None] = lambda _: None,
) -> tuple[pd.DataFrame, CodebookMapping, dict[str, str | None]]:
    """Replace or supplement one parent code and recode only its assigned rows."""

    models = model_config or ModelConfig()
    coding = coding_config or CodingConfig()
    working = dataframe.copy(deep=True)
    working_codebook = copy.deepcopy(codebook)
    parent = next(
        (code for code in working_codebook["codes"] if code["name"] == parent_code),
        None,
    )
    if parent is None:
        raise ValueError(f'"{parent_code}" not in codebook.')
    proposed = [str(value).strip() for value in (subcodes or []) if str(value).strip()]
    if len(proposed) < 2:
        parent_column = f"code_{parent_code}"
        if parent_column not in working.columns:
            raise KeyError(f'"{parent_column}" not found. Run coding first.')
        affected_text = working.loc[working[parent_column] == 1, text_column].tolist()
        if len(affected_text) < 2:
            raise ValueError(
                f'Only {len(affected_text)} response(s) carry "{parent_code}". Need ≥ 2 to split.'
            )
        sample = affected_text[:30]
        existing = [
            str(code["name"]) for code in working_codebook["codes"] if code["name"] != parent_code
        ]
        prompt = (
            "You are a qualitative research expert.\n\n"
            f"CODEBOOK OUTPUT LANGUAGE: {_language_name(working_codebook)}.\n"
            f'CONTEXT: {survey_context}\n\nThe code "{parent_code}" is too broad. '
            f"Here are {len(sample)} responses assigned to it:\n"
            + "\n".join(f'{index + 1}. "{text}"' for index, text in enumerate(sample))
            + "\n\nEXISTING CODE NAMES (do NOT reuse any of these):\n"
            + "\n".join(f"- {name}" for name in existing)
            + f"\n\nPropose exactly {n_subcodes_proposed} distinct and mutually exclusive "
            "sub-codes with short names.\nReturn ONLY valid JSON:\n"
            '{"subcodes": ["Name 1", "Name 2", "..."]}'
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
            max_tokens=500,
        )
        try:
            parsed = json.loads(extract_json(content))
            proposed = [
                str(value).strip() for value in parsed.get("subcodes", []) if str(value).strip()
            ]
        except (json.JSONDecodeError, TypeError, ValueError, AttributeError):
            proposed = []
        if not proposed:
            raise ValueError("Model returned no sub-codes.")
    if len(proposed) < 2:
        raise ValueError("Need ≥ 2 sub-codes to split.")
    if len({name.lower() for name in proposed}) != len(proposed):
        raise ValueError(f"Duplicate sub-code names are not allowed: {proposed}")

    existing_names = {
        str(code["name"]).lower()
        for code in working_codebook["codes"]
        if code["name"] != parent_code
    }
    resolved: list[str] = []
    for name in proposed:
        candidate = name
        if candidate.lower() in existing_names or candidate.lower() in {
            value.lower() for value in resolved
        }:
            candidate = f"{parent_code} - {name}"
            number = 2
            while candidate.lower() in existing_names or candidate.lower() in {
                value.lower() for value in resolved
            }:
                candidate = f"{parent_code} - {name} ({number})"
                number += 1
        resolved.append(candidate)

    requires_ids = any(
        clean_code_id(code.get(CODE_ID_FIELD, "")) for code in working_codebook["codes"]
    )
    manual_ids = normalize_manual_id_list(subcode_ids, len(resolved), "subcode_ids")
    parent_id = clean_code_id(parent.get(CODE_ID_FIELD, ""))
    if requires_ids:
        reserved = existing_code_ids(working_codebook)
        prefix = parent_id or slugify_for_code_id(parent_code, default="SPLIT", max_len=24)
        final_ids: list[str] = []
        for name, manual_id in zip(resolved, manual_ids, strict=True):
            if manual_id:
                if manual_id in reserved:
                    raise ValueError(f"subcode_ids contains an existing ID: {manual_id}")
                reserved.add(manual_id)
                final_ids.append(manual_id)
            else:
                final_ids.append(
                    auto_code_id_for_new_code(
                        working_codebook,
                        name,
                        prefix=prefix,
                        existing_ids=reserved,
                    )
                )
    else:
        final_ids = [""] * len(resolved)
        parent_id = ""

    definitions = [str(value).strip() for value in (subcode_definitions or [])]
    if definitions and len(definitions) != len(resolved):
        raise ValueError("subcode_definitions must be blank or have the same length as subcodes.")
    definitions = definitions or [""] * len(resolved)
    missing_definitions = [
        name for name, definition in zip(resolved, definitions, strict=True) if not definition
    ]
    if missing_definitions and not enrich_subcodes:
        raise ValueError(
            "Split-derived codes require definitions. Missing definitions for: "
            f"{missing_definitions}"
        )
    split_codebook: CodebookMapping = {
        "version": "split-draft",
        "multi_label": working_codebook.get("multi_label", True),
        "codebook_language": working_codebook.get("codebook_language", "fr"),
        "codes": [
            make_code_entry(
                name,
                code_id=identifier,
                definition=definition,
                inclusion_criteria=[],
                exclusion_criteria=[],
                example_verbatims=[],
                parent_code=parent_code,
                parent_code_id=parent_id,
                source="manual_split" if subcodes else "ai_split_proposal",
            )
            for name, identifier, definition in zip(
                resolved,
                final_ids,
                definitions,
                strict=True,
            )
        ],
    }
    validate_codebook(split_codebook)
    if enrich_subcodes:
        enrich_derived_codebook(
            complete,
            split_codebook,
            survey_context=survey_context,
            model_config=models,
            fallback_parent_code=parent_code,
        )
    else:
        _apply_definition_fallbacks(
            split_codebook,
            survey_context=survey_context,
            parent_code=parent_code,
            reason="deterministic_fallback_without_ai_enrichment",
        )

    parent_column = f"code_{parent_code}"
    if parent_column not in working.columns:
        raise KeyError(f'"{parent_column}" not found. Run coding first.')
    affected = working.index[working[parent_column] == 1]
    for code in split_codebook["codes"]:
        working[f"code_{code['name']}"] = 0
        working[f"conf_{code['name']}"] = 0.0
    normalization_codes: list[dict[str, Any]] = []
    for code in working_codebook["codes"]:
        if code["name"] == parent_code:
            if preserve_parent:
                normalization_codes.append(copy.deepcopy(code))
            normalization_codes.extend(copy.deepcopy(split_codebook["codes"]))
        else:
            normalization_codes.append(copy.deepcopy(code))
    normalization_codebook = {
        **working_codebook,
        "codes": normalization_codes,
        "max_codes_per_response": working_codebook.get(
            "max_codes_per_response",
            coding.maximum_codes_per_response,
        ),
    }
    if len(affected):
        recoded = code_batch(
            complete,
            working.loc[affected, text_column].astype(str).tolist(),
            split_codebook,
            coding_config=coding,
            model_config=models,
            sleep=sleep,
        )
        other = get_other_code_name(working_codebook)
        for index, raw_result in zip(affected, recoded, strict=True):
            previous = _previous_entries(working, index, working_codebook)
            if parent_code not in {
                entry.get("code") for entry in previous if isinstance(entry, dict)
            }:
                previous = _previous_entries(
                    working.drop(columns=["coding_result"], errors="ignore"),
                    index,
                    working_codebook,
                )
            split_entries = raw_result.get("codes", []) if isinstance(raw_result, dict) else []
            combined = _combine_split_entries(
                previous,
                split_entries if isinstance(split_entries, list) else [],
                parent_code,
                preserve_parent=preserve_parent,
            )
            normalized = normalize_coding_result(
                {"codes": combined, "split_recode_raw": copy.deepcopy(raw_result)},
                normalization_codebook,
                config=coding,
            )
            for code in normalization_codes:
                name = str(code["name"])
                if f"code_{name}" in working.columns:
                    working.at[index, f"code_{name}"] = 0
                if f"conf_{name}" in working.columns:
                    working.at[index, f"conf_{name}"] = 0.0
            selection = [entry["code"] for entry in normalized.get("codes", [])]
            for entry in normalized.get("codes", []):
                name = str(entry["code"])
                if f"code_{name}" not in working.columns:
                    continue
                working.at[index, f"code_{name}"] = 1
                working.at[index, f"conf_{name}"] = (
                    safe_confidence(entry["confidence"]) if "confidence" in entry else np.nan
                )
            working.at[index, "coding_result"] = json.dumps(
                normalized,
                ensure_ascii=False,
            )
            if "coding_status" in working.columns:
                working.at[index, "coding_status"] = (
                    "catch_all" if selection == [other] else "coded"
                )
    if not preserve_parent:
        working.drop(
            columns=[
                column
                for column in (f"code_{parent_code}", f"conf_{parent_code}")
                if column in working.columns
            ],
            inplace=True,
        )
    updated_codes: list[dict[str, Any]] = []
    for code in working_codebook["codes"]:
        if code["name"] == parent_code:
            if preserve_parent:
                updated_codes.append(code)
            updated_codes.extend(split_codebook["codes"])
        else:
            updated_codes.append(code)
    updated_codebook = {
        **working_codebook,
        "codes": updated_codes,
        "version": f"{working_codebook.get('version', '1.0')}+split",
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


def split_codes(
    dataframe: pd.DataFrame,
    codebook: CodebookMapping,
    complete: TextCompletion,
    split_configs: Sequence[dict[str, Any]],
    *,
    preserve_parent: bool = False,
    survey_context: str = "",
    text_column: str = "final_text_fr",
    output_dir: Path,
    output_file: str = "split.xlsx",
    model_config: ModelConfig | None = None,
    coding_config: CodingConfig | None = None,
    include_charts: bool = True,
    sleep: Callable[[float], None] = lambda _: None,
) -> tuple[pd.DataFrame, CodebookMapping, list[dict[str, Any]]]:
    """Apply one or more validated split configurations sequentially."""

    if not isinstance(split_configs, Sequence) or not split_configs:
        raise ValueError("split_configs must be a non-empty list.")
    working = dataframe.copy(deep=True)
    working_codebook = copy.deepcopy(codebook)
    outputs: list[dict[str, Any]] = []
    for position, config in enumerate(split_configs, 1):
        if not isinstance(config, dict):
            raise ValueError(f"Split config #{position} must be a dictionary.")
        parent = str(config.get("parent_code", "")).strip()
        if not parent:
            raise ValueError(f"Split config #{position} is missing parent_code.")
        step_file = output_file
        if len(split_configs) > 1:
            path = Path(output_file)
            step_file = (
                f"{path.stem}_{position:02d}_"
                f"{slugify_for_code_id(parent, default='parent').lower()}"
                f"{path.suffix or '.xlsx'}"
            )
        working, working_codebook, step_outputs = split_code(
            working,
            working_codebook,
            complete,
            parent,
            subcodes=config.get("subcodes", []),
            subcode_ids=config.get("subcode_ids", []),
            subcode_definitions=config.get("subcode_definitions", []),
            n_subcodes_proposed=int(config.get("n_subcodes_proposed", 3)),
            enrich_subcodes=bool(config.get("enrich", True)),
            survey_context=survey_context,
            text_column=text_column,
            output_dir=output_dir,
            output_file=step_file,
            preserve_parent=bool(config.get("preserve_parent", preserve_parent)),
            model_config=model_config,
            coding_config=coding_config,
            include_charts=include_charts,
            sleep=sleep,
        )
        outputs.append(step_outputs)
    if len(split_configs) > 1:
        final_outputs = generate_reports(
            working,
            working_codebook,
            output_dir=output_dir,
            file_stem=Path(output_file).stem,
            text_column=text_column,
            output_file=output_file,
            include_charts=include_charts,
        )
        outputs.append({"final_combined_output": final_outputs})
    return working, working_codebook, outputs


@dataclass(frozen=True, slots=True)
class SplitRunResult:
    dataframe: pd.DataFrame
    codebook: CodebookMapping
    outputs: list[dict[str, Any]]
    did_run: bool


def apply_confirmed_splits(
    dataframe: pd.DataFrame,
    codebook: CodebookMapping,
    complete: TextCompletion,
    split_configs: Sequence[dict[str, Any]],
    *,
    confirmed: bool,
    **kwargs: Any,
) -> SplitRunResult:
    """Apply only an explicitly confirmed nonempty plan; otherwise return fresh copies."""

    if confirmed and not split_configs:
        raise ValueError("confirmed=True but split_configs is empty.")
    if not confirmed or not split_configs:
        return SplitRunResult(
            dataframe.copy(deep=True),
            copy.deepcopy(codebook),
            [],
            False,
        )
    result = split_codes(
        dataframe,
        codebook,
        complete,
        split_configs,
        **kwargs,
    )
    return SplitRunResult(*result, True)
