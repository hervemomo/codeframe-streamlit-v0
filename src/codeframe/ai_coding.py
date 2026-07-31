"""Deduplicated batch coding and deterministic assignment normalization."""

import json
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from codeframe.codebook import (
    NORMALIZATION_RULE_VERSION,
    OTHER_FALLBACK_CONFIDENCE,
    CodebookMapping,
    add_codes_column,
    clean_code_id,
    format_codebook_for_prompt,
    format_codebook_for_prompt_compact,
    generate_codebook,
    get_other_code_name,
    safe_confidence,
)
from codeframe.config import ClusteringConfig, CodingConfig, LanguageConfig, ModelConfig
from codeframe.embeddings import EmbeddingClient
from codeframe.exports import save_codebook_json
from codeframe.llm_client import TextCompletion
from codeframe.reporting import generate_reports
from codeframe.usage import UsageTracker


def deduplicate_texts(texts: Sequence[str]) -> tuple[list[str], list[int]]:
    """Return unique texts and an original-index-to-unique-index map."""

    seen: dict[str, int] = {}
    unique: list[str] = []
    index_map: list[int] = []
    for text in texts:
        if text not in seen:
            seen[text] = len(unique)
            unique.append(text)
        index_map.append(seen[text])
    return unique, index_map


def effective_max_codes_per_response(
    codebook: CodebookMapping,
    configured_max: int | None = None,
    *,
    config: CodingConfig | None = None,
) -> int:
    """Return configured cap, forced to one for mutually exclusive codebooks."""

    default = (config or CodingConfig()).maximum_codes_per_response
    maximum = (
        configured_max
        if configured_max is not None
        else codebook.get("max_codes_per_response", default)
    )
    if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum < 1:
        raise ValueError("max_codes_per_response must be an integer of at least 1.")
    return maximum if codebook.get("multi_label", True) else 1


def coding_instruction(
    codebook: CodebookMapping,
    *,
    config: CodingConfig | None = None,
) -> str:
    """Build the notebook instruction enforcing assignment and catch-all rules."""

    maximum = effective_max_codes_per_response(codebook, config=config)
    if codebook.get("multi_label", True):
        base = (
            f"Assign at most {maximum} substantive codes. Select only the most relevant "  # nosec B608
            "codes and return them from most to least relevant."
        )
    else:
        base = "Assign EXACTLY ONE code."
    other = get_other_code_name(codebook)
    if other:
        return (
            f'{base} If no specific code applies, assign "{other}". '
            "The catch-all code is exclusive and must never be combined with a substantive "
            "code. Use ONLY code names exactly as written in the codebook."
        )
    return f"{base} Use ONLY code names exactly as written in the codebook."


def normalize_coding_result(
    result: object,
    codebook: CodebookMapping,
    *,
    configured_max: int | None = None,
    config: CodingConfig | None = None,
) -> dict[str, Any]:
    """Normalize one raw result using the notebook's authoritative rules."""

    raw_result = result if isinstance(result, dict) else {"codes": []}
    reserved = {
        "codes",
        "invalid_returned_codes",
        "duplicate_returned_codes",
        "removed_catch_all_from_mixed_selection",
        "dropped_due_to_max_codes",
        "fallback_reason",
        "max_codes_per_response",
        "normalization_rule_version",
    }
    normalized = {key: value for key, value in raw_result.items() if key not in reserved}
    raw_codes = raw_result.get("codes", [])
    if not isinstance(raw_codes, list):
        raw_codes = []
    allowed_names = {str(code["name"]) for code in codebook.get("codes", [])}
    name_by_id = {
        clean_code_id(code.get("code_id", "")): str(code["name"])
        for code in codebook.get("codes", [])
        if clean_code_id(code.get("code_id", ""))
    }
    other = get_other_code_name(codebook)
    maximum = effective_max_codes_per_response(
        codebook,
        configured_max,
        config=config,
    )
    substantive: list[dict[str, Any]] = []
    invalid: list[str] = []
    duplicate: list[str] = []
    seen: set[str] = set()
    catch_all_returned = False
    for raw_entry in raw_codes:
        if isinstance(raw_entry, str):
            entry: dict[str, Any] = {"code": raw_entry.strip()}
        elif isinstance(raw_entry, dict):
            entry = dict(raw_entry)
            entry["code"] = str(entry.get("code", "")).strip()
        else:
            invalid.append(str(raw_entry))
            continue
        name = str(entry.get("code", ""))
        if name and name not in allowed_names and name in name_by_id:
            name = name_by_id[name]
            entry["code"] = name
        if not name or name not in allowed_names:
            if name:
                invalid.append(name)
            continue
        if name in seen:
            duplicate.append(name)
            continue
        seen.add(name)
        if other and name == other:
            catch_all_returned = True
            continue
        if "confidence" in entry:
            entry["confidence"] = safe_confidence(entry.get("confidence", 0.0))
        substantive.append(entry)
    dropped = substantive[maximum:]
    substantive = substantive[:maximum]
    if substantive:
        normalized["codes"] = substantive
        if catch_all_returned:
            normalized["removed_catch_all_from_mixed_selection"] = True
    elif other:
        normalized["codes"] = [
            {
                "code": other,
                "confidence": OTHER_FALLBACK_CONFIDENCE,
                "fallback": True,
            }
        ]
        normalized["fallback_reason"] = (
            "Zero valid substantive codes remained after validation; "
            "assigned catch-all category only."
        )
    else:
        normalized["codes"] = []
    if invalid:
        normalized["invalid_returned_codes"] = invalid
    if duplicate:
        normalized["duplicate_returned_codes"] = duplicate
    if dropped:
        normalized["dropped_due_to_max_codes"] = [entry["code"] for entry in dropped]
    normalized["max_codes_per_response"] = maximum
    normalized["normalization_rule_version"] = NORMALIZATION_RULE_VERSION
    return normalized


def _codebook_text(codebook: CodebookMapping, config: CodingConfig) -> str:
    return (
        format_codebook_for_prompt_compact(codebook)
        if config.use_compact_codebook
        else format_codebook_for_prompt(codebook)
    )


def _strip_json_fence(content: str) -> str:
    stripped = re.sub(r"^```(?:json)?\n?", "", content.strip())
    return re.sub(r"\n?```$", "", stripped)


def code_single(
    complete: TextCompletion,
    text: str,
    codebook: CodebookMapping,
    *,
    coding_config: CodingConfig | None = None,
    model_config: ModelConfig | None = None,
) -> dict[str, Any]:
    """Code one response as the batch-parse fallback."""

    coding = coding_config or CodingConfig()
    models = model_config or ModelConfig()
    schema = (
        '{"codes":[{"code":"<name>","confidence":0.0}],"reasoning":"brief"}'
        if coding.save_reasoning
        else '{"codes":[{"code":"<name>","confidence":0.0}]}'
    )
    prompt = (
        "Assign codes to this survey response.\n\n"
        "CODEBOOK (use ONLY these codes):\n"
        f"{_codebook_text(codebook, coding)}\n\n"
        f"RESPONSE: {text}\n\n"
        f"INSTRUCTIONS: {coding_instruction(codebook, config=coding)}\n"
        "Include confidence 0.0-1.0. Return ONLY raw JSON:\n"
        f"{schema}"
    )
    content = complete(
        model=models.coding_model,
        messages=[
            {"role": "system", "content": "Survey coder. Return ONLY raw JSON."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=450 if coding.save_reasoning else 250,
    )
    try:
        parsed = json.loads(_strip_json_fence(content))
        return parsed if isinstance(parsed, dict) else {"codes": []}
    except json.JSONDecodeError:
        return {"codes": []}


def code_batch(
    complete: TextCompletion,
    texts: Sequence[str],
    codebook: CodebookMapping,
    *,
    coding_config: CodingConfig | None = None,
    model_config: ModelConfig | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> list[dict[str, Any]]:
    """Code unique responses in batches and fall back per item on malformed output."""

    coding = coding_config or CodingConfig()
    models = model_config or ModelConfig()
    unique_texts, index_map = deduplicate_texts(texts)
    unique_results: list[dict[str, Any]] = []
    instruction = coding_instruction(codebook, config=coding)
    schema = (
        '[{"response_num":1,"codes":[{"code":"<name>","confidence":0.0}],"reasoning":"brief"}]'
        if coding.save_reasoning
        else '[{"response_num":1,"codes":[{"code":"<name>","confidence":0.0}]}]'
    )
    for start in range(0, len(unique_texts), coding.coding_batch_size):
        batch = unique_texts[start : start + coding.coding_batch_size]
        numbered = "".join(f'\n[{index}] "{text}"\n' for index, text in enumerate(batch, 1))
        per_response_budget = 160 if coding.save_reasoning else 90
        output_tokens = min(3500, max(400, len(batch) * per_response_budget))
        prompt = (
            "You are a precise qualitative survey coder.\n\n"
            "CODEBOOK (use ONLY these codes):\n"
            f"{_codebook_text(codebook, coding)}\n\n"
            f"RESPONSES:\n{numbered}\n\n"
            f"INSTRUCTIONS: {instruction}\n"
            "Include confidence 0.0-1.0.\n"
            "Return a JSON array -- one object per response, in the same order:\n"
            f"{schema}"
        )
        content = complete(
            model=models.coding_model,
            messages=[
                {"role": "system", "content": "Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=output_tokens,
        )
        try:
            parsed = json.loads(_strip_json_fence(content))
            if not isinstance(parsed, list) or len(parsed) != len(batch):
                size: object = len(parsed) if isinstance(parsed, list) else type(parsed)
                raise ValueError(f"Expected {len(batch)} items, got {size}")
            unique_results.extend(
                item if isinstance(item, dict) else {"codes": []} for item in parsed
            )
            sleep(0.3)
        except (json.JSONDecodeError, ValueError, TypeError):
            for text in batch:
                unique_results.append(
                    code_single(
                        complete,
                        text,
                        codebook,
                        coding_config=coding,
                        model_config=models,
                    )
                )
                sleep(0.2)
    return [unique_results[index] for index in index_map]


def apply_codes_to_dataframe(
    complete: TextCompletion,
    dataframe: pd.DataFrame,
    codebook: CodebookMapping,
    *,
    text_column: str = "final_text_fr",
    coding_config: CodingConfig | None = None,
    model_config: ModelConfig | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> pd.DataFrame:
    """Apply the codebook and append indicator, confidence, and audit JSON columns."""

    coding = coding_config or CodingConfig()
    results = code_batch(
        complete,
        dataframe[text_column].tolist(),
        codebook,
        coding_config=coding,
        model_config=model_config,
        sleep=sleep,
    )
    for code in codebook["codes"]:
        dataframe[f"code_{code['name']}"] = 0
        dataframe[f"conf_{code['name']}"] = 0.0
    normalized_results: list[dict[str, Any]] = []
    for index, result in zip(dataframe.index, results, strict=True):
        normalized = normalize_coding_result(result, codebook, config=coding)
        for selection in normalized.get("codes", []):
            name = str(selection.get("code", "")).strip()
            code_column = f"code_{name}"
            confidence_column = f"conf_{name}"
            if not name or code_column not in dataframe.columns:
                continue
            confidence = safe_confidence(selection.get("confidence", 0.0))
            dataframe.at[index, code_column] = 1
            dataframe.at[index, confidence_column] = confidence
            selection["confidence"] = confidence
        normalized_results.append(normalized)
    dataframe["coding_result"] = [
        json.dumps(result, ensure_ascii=False) for result in normalized_results
    ]
    return dataframe


@dataclass(frozen=True, slots=True)
class AIWorkflowResult:
    """Complete AI-path artifacts handed to the UI layer."""

    dataframe: pd.DataFrame
    codebook: CodebookMapping
    labels: NDArray[np.integer[Any]]
    representatives: dict[int, list[str]]
    cluster_sizes: dict[int, int]
    outputs: dict[str, str | None]


type ThemeDiscovery = Callable[
    [pd.DataFrame, EmbeddingClient],
    tuple[
        pd.DataFrame,
        NDArray[np.integer[Any]],
        dict[int, list[str]],
        dict[int, int],
    ],
]


def run_ai_codebook_workflow(
    dataframe: pd.DataFrame,
    embedding_client: EmbeddingClient,
    complete: TextCompletion,
    *,
    output_dir: Path,
    file_stem: str,
    survey_context: str,
    text_column: str = "final_text_fr",
    language_config: LanguageConfig | None = None,
    model_config: ModelConfig | None = None,
    coding_config: CodingConfig | None = None,
    clustering_config: ClusteringConfig | None = None,
    theme_discovery: ThemeDiscovery | None = None,
    include_charts: bool = True,
    include_excel: bool = True,
    usage_tracker: UsageTracker | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> AIWorkflowResult:
    """Run clustering, generation, coding, summaries, and notebook report exports."""

    coding = coding_config or CodingConfig(mode="ai")
    if coding.mode != "ai":
        raise ValueError("AI codebook workflow requires coding mode 'ai'.")
    if theme_discovery is None:
        from codeframe.clustering import discover_themes

        clustered, labels, representatives, cluster_sizes = discover_themes(
            dataframe,
            embedding_client,
            text_column=text_column,
            config=clustering_config,
            model_config=model_config,
            usage_tracker=usage_tracker,
        )
    else:
        clustered, labels, representatives, cluster_sizes = theme_discovery(
            dataframe,
            embedding_client,
        )
    target_codes = len(representatives)
    if coding.target_code_cap is not None:
        target_codes = min(target_codes, coding.target_code_cap)
    codebook = generate_codebook(
        complete,
        representatives,
        survey_context=survey_context,
        target_codes=target_codes,
        multi_label=True,
        cluster_sizes=cluster_sizes,
        language_config=language_config,
        model_config=model_config,
        coding_config=coding,
    )
    save_codebook_json(
        codebook,
        output_dir=output_dir,
        file_name=f"{file_stem}_codebook_s2.json",
    )
    coded = apply_codes_to_dataframe(
        complete,
        clustered,
        codebook,
        text_column=text_column,
        coding_config=coding,
        model_config=model_config,
        sleep=sleep,
    )
    add_codes_column(coded, codebook)
    outputs = generate_reports(
        coded,
        codebook,
        output_dir=output_dir,
        file_stem=file_stem,
        text_column=text_column,
        output_file=f"{file_stem}_s2.xlsx",
        include_charts=include_charts,
        include_excel=include_excel,
    )
    outputs["codebook"] = str(output_dir / f"{file_stem}_codebook_s2.json")
    return AIWorkflowResult(
        dataframe=coded,
        codebook=codebook,
        labels=labels,
        representatives=representatives,
        cluster_sizes=cluster_sizes,
        outputs=outputs,
    )
