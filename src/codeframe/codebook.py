"""Codebook validation, rendering, generation, and shared deterministic helpers."""

import json
import math
import re
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, cast

import pandas as pd

from codeframe.config import CodingConfig, LanguageConfig, ModelConfig
from codeframe.llm_client import TextCompletion

type CodebookMapping = dict[str, Any]
type CodeColumn = tuple[str, str, str]

CODE_ID_FIELD = "code_id"
OTHER_FALLBACK_CONFIDENCE = 0.50
NORMALIZATION_RULE_VERSION = "notebook-assignment-normalization-v1"


def clean_code_id(value: object) -> str:
    """Return a stable string code ID, preserving notebook spreadsheet behavior."""

    if value is None:
        return ""
    try:
        is_missing = bool(pd.isna(cast(Any, value)))
    except Exception:
        is_missing = False
    if is_missing:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def codebook_has_code_ids(codebook: CodebookMapping) -> bool:
    """Return whether any code carries a nonblank governed ID."""

    return any(clean_code_id(code.get(CODE_ID_FIELD, "")) for code in codebook.get("codes", []))


def codebook_requires_manual_ids(codebook: CodebookMapping) -> bool:
    """Return whether all newly added codes require governed IDs."""

    return codebook_has_code_ids(codebook)


def canonical_code_key(value: object) -> str:
    """Normalize names and optional ``[ID]`` prefixes for robust matching."""

    text = _clean_text(value)
    text = re.sub(r"^\[[^\]]+\]\s*", "", text)
    return re.sub(r"\s+", " ", text).strip().casefold()


def same_code_name_set(left: Sequence[object], right: Sequence[object]) -> bool:
    """Compare two code-name collections after normalization and without ordering."""

    return {canonical_code_key(value) for value in left if canonical_code_key(value)} == {
        canonical_code_key(value) for value in right if canonical_code_key(value)
    }


def existing_code_ids(codebook: CodebookMapping) -> set[str]:
    """Return all nonblank governed IDs."""

    return {
        clean_code_id(code.get(CODE_ID_FIELD, ""))
        for code in codebook.get("codes", [])
        if clean_code_id(code.get(CODE_ID_FIELD, ""))
    }


def slugify_for_code_id(value: object, default: str = "CODE", max_len: int = 48) -> str:
    """Create the notebook's stable uppercase ASCII ID token."""

    text = unicodedata.normalize("NFKD", _clean_text(value))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").upper()
    text = re.sub(r"_+", "_", text)
    if not text:
        text = default or ""
    text = text[:max_len].strip("_")
    return text or default or ""


def make_unique_code_id(
    base: object,
    existing_ids: set[str],
    max_len: int = 64,
) -> str:
    """Return a unique deterministic ID with ``_02``, ``_03`` collision suffixes."""

    normalized = slugify_for_code_id(base, default="CODE", max_len=max_len) or "CODE"
    candidate = normalized
    suffix_number = 2
    while candidate in existing_ids:
        suffix = f"_{suffix_number:02d}"
        candidate = f"{normalized[: max_len - len(suffix)].rstrip('_')}{suffix}"
        suffix_number += 1
    existing_ids.add(candidate)
    return candidate


def auto_code_id_for_new_code(
    codebook: CodebookMapping,
    code_name: object,
    *,
    prefix: object = "",
    existing_ids: set[str] | None = None,
) -> str:
    """Generate a stable collision-checked ID for split/merge-derived codes."""

    reserved = existing_ids if existing_ids is not None else existing_code_ids(codebook)
    normalized_prefix = slugify_for_code_id(prefix, default="", max_len=24) if prefix else ""
    name_part = slugify_for_code_id(code_name, default="CODE", max_len=40)
    base = f"{normalized_prefix}_{name_part}" if normalized_prefix else name_part
    return make_unique_code_id(base, reserved)


def normalize_manual_id_list(
    values: Sequence[object] | None,
    expected_len: int,
    label: str,
) -> list[str]:
    """Normalize optional manual IDs while allowing per-item auto-generation."""

    identifiers = [clean_code_id(value) for value in (values or [])]
    if identifiers and len(identifiers) != expected_len:
        raise ValueError(f"{label} must be blank or have exactly {expected_len} item(s).")
    return identifiers or [""] * expected_len


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    try:
        is_missing = bool(pd.isna(cast(Any, value)))
    except Exception:
        is_missing = False
    if is_missing:
        return ""
    return str(value).strip()


def safe_confidence(value: object, default: float = 0.0) -> float:
    """Return a finite numeric confidence clamped to ``[0, 1]``."""

    try:
        number = float(default if value is None or value == "" else cast(Any, value))
    except (TypeError, ValueError):
        number = float(default)
    if not math.isfinite(number):
        number = float(default)
    return max(0.0, min(1.0, number))


def code_reference(code: Mapping[str, Any]) -> str:
    """Render a code name with its optional governed ID."""

    code_id = clean_code_id(code.get(CODE_ID_FIELD, ""))
    name = _clean_text(code.get("name", ""))
    return f"[{code_id}] {name}" if code_id else name


def make_code_entry(
    name: object,
    *,
    code_id: object = "",
    definition: object = "",
    inclusion_criteria: Sequence[str] | None = None,
    exclusion_criteria: Sequence[str] | None = None,
    example_verbatims: Sequence[str] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Create a normalized code entry while preserving an optional ID."""

    entry: dict[str, Any] = {
        "name": _clean_text(name),
        "definition": _clean_text(definition),
        "inclusion_criteria": list(inclusion_criteria or []),
        "exclusion_criteria": list(exclusion_criteria or []),
        "example_verbatims": list(example_verbatims or []),
    }
    normalized_id = clean_code_id(code_id)
    if normalized_id:
        entry[CODE_ID_FIELD] = normalized_id
    entry.update({key: value for key, value in extra.items() if value not in (None, "")})
    return entry


def format_codebook_for_prompt(codebook: CodebookMapping) -> str:
    """Render the notebook's full numbered codebook prompt."""

    lines: list[str] = []
    for index, code in enumerate(codebook["codes"], 1):
        lines.append(f"{index}. **{code_reference(code)}**")
        if code.get("definition"):
            lines.append(f"   Definition: {code['definition']}")
        if code.get("inclusion_criteria"):
            lines.append(f"   Include if: {'; '.join(code['inclusion_criteria'])}")
        if code.get("exclusion_criteria"):
            lines.append(f"   Exclude if: {'; '.join(code['exclusion_criteria'])}")
        lines.append("")
    return "\n".join(lines)


def format_codebook_for_prompt_compact(codebook: CodebookMapping) -> str:
    """Render definitions and criteria inline while omitting examples."""

    lines: list[str] = []
    for index, code in enumerate(codebook["codes"], 1):
        reference = code_reference(code)
        definition = str(code.get("definition", "")).strip()
        line = f"{index}. {reference}: {definition}" if definition else f"{index}. {reference}"
        inclusion = code.get("inclusion_criteria") or []
        exclusion = code.get("exclusion_criteria") or []
        if inclusion:
            line += f" | Include if: {'; '.join(inclusion)}"
        if exclusion:
            line += f" | Exclude if: {'; '.join(exclusion)}"
        lines.append(line)
    return "\n".join(lines)


def extract_json(raw: str) -> str:
    """Extract the first fenced or balanced JSON value from model text."""

    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    start = -1
    opening = ""
    closing = ""
    for index, character in enumerate(text):
        if character in "{[":
            start = index
            opening = character
            closing = "}" if character == "{" else "]"
            break
    if start == -1:
        return text
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        character = text[index]
        if in_string:
            if escape:
                escape = False
            elif character == "\\":
                escape = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character == opening:
            depth += 1
        elif character == closing:
            depth -= 1
            if depth == 0:
                return text[start : index + 1].strip()
    return text[start:].strip()


def validate_codebook(codebook: CodebookMapping) -> None:
    """Validate required fields, unique names, and coherent governed IDs."""

    codes = codebook.get("codes")
    if not isinstance(codes, list) or not codes:
        raise ValueError("Codebook missing or empty 'codes' list.")
    required = {
        "name",
        "definition",
        "inclusion_criteria",
        "exclusion_criteria",
        "example_verbatims",
    }
    names: list[str] = []
    identifiers: list[str] = []
    has_ids = codebook_has_code_ids(codebook)
    for index, code in enumerate(codes):
        missing = required - code.keys()
        if missing:
            raise ValueError(f"Code #{index + 1} missing fields: {missing}")
        name = _clean_text(code.get("name", ""))
        if not name:
            raise ValueError(f"Code #{index + 1} has a blank name.")
        names.append(name)
        if has_ids:
            identifier = clean_code_id(code.get(CODE_ID_FIELD, ""))
            if not identifier:
                raise ValueError(
                    f'Code "{name}" is missing code_id. Because this codebook has '
                    "a code ID column, every code must have an ID."
                )
            code[CODE_ID_FIELD] = identifier
            identifiers.append(identifier)
    duplicate_names = sorted({name for name in names if names.count(name) > 1})
    if duplicate_names:
        raise ValueError(
            "Duplicate code names are not supported because columns are name-based: "
            f"{duplicate_names}"
        )
    duplicate_ids = sorted(
        {identifier for identifier in identifiers if identifiers.count(identifier) > 1}
    )
    if duplicate_ids:
        raise ValueError(f"Duplicate code IDs found: {duplicate_ids}")


def get_default_other_code_name(language_code: str = "fr") -> str:
    """Return the notebook's localized catch-all name."""

    return (
        "Other / Not classifiable"
        if language_code.lower().strip() == "en"
        else "Autre / Non classifiable"
    )


def get_other_code_name(
    codebook: CodebookMapping,
    preferred_name: str | None = None,
) -> str | None:
    """Return the exact existing catch-all name using case-insensitive matching."""

    language_code = str(codebook.get("codebook_language", "fr"))
    expected = (preferred_name or get_default_other_code_name(language_code)).strip().lower()
    for code in codebook.get("codes", []):
        name = str(code.get("name", "")).strip()
        if name.lower() == expected:
            return name
    return None


def _default_other_metadata(language_code: str) -> dict[str, Any]:
    if language_code == "en":
        return {
            "definition": (
                "Valid response that does not clearly match any other code in the codebook."
            ),
            "inclusion_criteria": [
                "Use only when no specific code applies.",
                "Use for ambiguous, off-topic, or non-classifiable responses.",
            ],
            "exclusion_criteria": [
                "Do not use if a more specific code applies.",
                "Do not use for blank or invalid responses already removed during preprocessing.",
            ],
        }
    return {
        "definition": (
            "Réponse valide qui ne correspond clairement à aucun autre code du livre de codes."
        ),
        "inclusion_criteria": [
            "Utiliser seulement lorsqu'aucun code spécifique ne s'applique.",
            "Utiliser pour les réponses ambiguës, hors sujet ou non classifiables.",
        ],
        "exclusion_criteria": [
            "Ne pas utiliser si un code plus spécifique s'applique.",
            "Ne pas utiliser pour les réponses vides ou invalides déjà retirées au prétraitement.",
        ],
    }


def ensure_other_code(
    codebook: CodebookMapping,
    *,
    other_name: str | None = None,
    other_code_id: object = "",
    language_code: str = "fr",
) -> CodebookMapping:
    """Ensure a catch-all exists without inventing an ID for governed codebooks."""

    if "codes" not in codebook or not isinstance(codebook["codes"], list):
        raise ValueError('Codebook must contain a list under key "codes".')
    selected_name = other_name or get_default_other_code_name(language_code)
    if get_other_code_name(codebook, selected_name) is not None:
        validate_codebook(codebook)
        return codebook
    if codebook_requires_manual_ids(codebook) and not clean_code_id(other_code_id):
        raise ValueError(
            f'Catch-all code "{selected_name}" is missing. Because this codebook has '
            "a code ID column, add the catch-all row to the source codebook with a "
            "valid ID, or pass other_code_id explicitly when Part 2 is implemented."
        )
    metadata = _default_other_metadata(language_code)
    codebook["codes"].append(
        make_code_entry(
            selected_name,
            code_id=other_code_id,
            definition=metadata["definition"],
            inclusion_criteria=metadata["inclusion_criteria"],
            exclusion_criteria=metadata["exclusion_criteria"],
            example_verbatims=[],
            source="system_catch_all",
        )
    )
    validate_codebook(codebook)
    return codebook


def format_clusters(representatives: Mapping[int, Sequence[str]]) -> str:
    """Format cluster verbatims exactly as the generation prompt expects."""

    lines: list[str] = []
    for cluster_id, samples in representatives.items():
        lines.append(f"\n### Cluster {cluster_id + 1}")
        lines.extend(f'{index}. "{sample}"' for index, sample in enumerate(samples, 1))
    return "\n".join(lines)


def apply_cluster_traceability(
    codebook: CodebookMapping,
    *,
    cluster_sizes: Mapping[int, int],
    other_name: str,
    expected_clusters: set[int],
) -> CodebookMapping:
    """Require every displayed cluster to map to exactly one substantive code."""

    claimed_by: dict[int, list[str]] = {}
    for code in codebook["codes"]:
        if code.get("name") == other_name:
            code["source_clusters"] = []
            code["estimated_response_count"] = 0
            continue
        raw = code.get("source_clusters")
        if not isinstance(raw, list) or not raw:
            raise ValueError(f'Code "{code.get("name", "")}" is missing source_clusters.')
        clusters = sorted(
            {
                int(cluster)
                for cluster in raw
                if isinstance(cluster, int | float) and int(cluster) in expected_clusters
            }
        )
        if not clusters:
            raise ValueError(f'Code "{code.get("name", "")}" has no valid source_clusters.')
        for cluster in clusters:
            claimed_by.setdefault(cluster, []).append(str(code.get("name", "")))
        code["source_clusters"] = clusters
        code["estimated_response_count"] = sum(
            cluster_sizes.get(cluster - 1, 0) for cluster in clusters
        )
    missing = sorted(expected_clusters - set(claimed_by))
    duplicated = sorted(cluster for cluster, names in claimed_by.items() if len(names) > 1)
    if missing:
        raise ValueError(f"Codebook is missing source_clusters coverage for cluster(s): {missing}")
    if duplicated:
        raise ValueError(f"Cluster(s) claimed by more than one code: {duplicated}")
    return codebook


def generate_codebook(
    complete: TextCompletion,
    representatives: Mapping[int, Sequence[str]],
    *,
    survey_context: str = "",
    target_codes: int | None = None,
    multi_label: bool = True,
    cluster_sizes: Mapping[int, int] | None = None,
    language_config: LanguageConfig | None = None,
    model_config: ModelConfig | None = None,
    coding_config: CodingConfig | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> CodebookMapping:
    """Generate, validate, and trace a codebook with one larger-budget retry."""

    language = language_config or LanguageConfig()
    models = model_config or ModelConfig()
    coding = coding_config or CodingConfig()
    language_code = language.codebook_language_code
    language_name = "English" if language_code == "en" else "French"
    other_name = get_default_other_code_name(language_code)
    context = survey_context or "Open-ended survey responses."
    code_instruction = (
        f"Create exactly {target_codes} distinct codes"
        if target_codes
        else "Create an appropriate number of distinct codes"
    )
    label_instruction = (
        "The codes must support multi-label coding."
        if multi_label
        else "The codes must be mutually exclusive."
    )
    cluster_numbers = sorted(cluster_id + 1 for cluster_id in representatives)
    cluster_range = f"{cluster_numbers[0]} to {cluster_numbers[-1]}" if cluster_numbers else "none"
    prompt = (
        "Analyze the groups and create a qualitative codebook.\n\n"
        f"CODEBOOK OUTPUT LANGUAGE: {language_name}.\n"
        "Write code names, definitions, criteria, example verbatims, and the "
        f"catch-all code in {language_name}.\n\n"
        f"CONTEXT:\n{context}\n\nGROUPS:\n{format_clusters(representatives)}\n\n"
        f"INSTRUCTIONS:\n1. {code_instruction}.\n2. {label_instruction}\n"
        "3. Merge groups whose themes overlap.\n"
        f'4. Add this exact catch-all code: "{other_name}".\n'
        "5. Keep the JSON concise to avoid truncation:\n"
        "   - code name: max 5 words\n"
        "   - definition: max 25 words\n"
        "   - inclusion_criteria: 2 to 3 short items\n"
        "   - exclusion_criteria: 1 to 2 short items\n"
        "   - example_verbatims: max 2 short examples\n"
        "   - no extra fields other than source_clusters\n"
        '6. For every code except the catch-all, include "source_clusters": the '
        f"Cluster number(s) above ({cluster_range}) it was authored from. If you "
        "merge overlapping groups into one code, list every merged cluster number "
        f"under that single code. Every cluster number from {cluster_range} must "
        "appear in exactly one code's source_clusters. The catch-all code must "
        "have an empty source_clusters list.\n\n"
        "Return ONLY valid JSON, with no Markdown and no text outside JSON:\n"
        '{"codes":[{"name":"...","definition":"...",'
        '"inclusion_criteria":["..."],"exclusion_criteria":["..."],'
        '"example_verbatims":["..."],"source_clusters":[1,2]}]}'
    )
    budgets = [coding.generation_max_tokens]
    if coding.generation_retry_max_tokens > coding.generation_max_tokens:
        budgets.append(coding.generation_retry_max_tokens)
    last_error: Exception | None = None
    last_raw = ""
    for attempt, budget in enumerate(budgets):
        retry_note = (
            ""
            if attempt == 0
            else (
                "\n\nIMPORTANT RETRY INSTRUCTION:\n"
                "The previous response was incomplete or invalid: truncated JSON, or "
                "missing/duplicate source_clusters coverage. Return a shorter, complete "
                "JSON object where every cluster number is covered by exactly one code. "
                "Keep all text very concise and do not include markdown."
            )
        )
        last_raw = complete(
            model=models.reasoning_model,
            messages=[
                {
                    "role": "system",
                    "content": ("Qualitative research expert. Return ONLY complete valid JSON."),
                },
                {"role": "user", "content": prompt + retry_note},
            ],
            temperature=models.reasoning_temperature,
            seed=models.reasoning_seed,
            max_tokens=budget,
        ).strip()
        try:
            parsed = json.loads(extract_json(last_raw))
            if not isinstance(parsed, dict):
                raise ValueError("Codebook response must be a JSON object.")
            result = cast(CodebookMapping, parsed)
            validate_codebook(result)
            ensure_other_code(
                result,
                other_name=other_name,
                language_code=language_code,
            )
            apply_cluster_traceability(
                result,
                cluster_sizes=cluster_sizes or {},
                other_name=other_name,
                expected_clusters=set(cluster_numbers),
            )
            result.update(
                {
                    "version": "1.0-draft",
                    "description": survey_context,
                    "multi_label": multi_label,
                    "codebook_language": language_code,
                    "generated_at": now().isoformat(),
                    "model": models.reasoning_model,
                }
            )
            return result
        except (json.JSONDecodeError, ValueError, TypeError) as error:
            last_error = error
    raise ValueError(
        "Codebook generation returned truncated or invalid JSON after automatic retry. "
        "Recommended fixes: increase generation_retry_max_tokens, reduce target_code_cap "
        "or reduce representatives_per_cluster.\n\n"
        f"Last error: {last_error}\n\nLast output tail for debugging:\n{last_raw[-800:]}"
    )


def get_code_columns(dataframe: pd.DataFrame, codebook: CodebookMapping) -> list[CodeColumn]:
    """Return notebook-ordered code/name/confidence columns that both exist."""

    return [
        (code["name"], f"code_{code['name']}", f"conf_{code['name']}")
        for code in codebook["codes"]
        if f"code_{code['name']}" in dataframe.columns
        and f"conf_{code['name']}" in dataframe.columns
    ]


def add_codes_column(
    dataframe: pd.DataFrame,
    codebook: CodebookMapping,
    separator: str = " | ",
) -> pd.DataFrame:
    """Rebuild code-name/ID/count/multi-label summaries without stale values."""

    for column in ("codes", "code_ids", "num_codes", "has_multi_label"):
        if column in dataframe.columns:
            dataframe.drop(columns=[column], inplace=True)
    entries = get_code_columns(dataframe, codebook)
    code_columns = [entry[1] for entry in entries]
    names = [entry[0] for entry in entries]
    identifiers_by_name = {
        code["name"]: clean_code_id(code.get(CODE_ID_FIELD, ""))
        for code in codebook.get("codes", [])
    }

    dataframe["codes_list"] = dataframe.apply(
        lambda row: [
            name for name, column in zip(names, code_columns, strict=True) if row[column] == 1
        ],
        axis=1,
    )
    dataframe["code_ids_list"] = dataframe["codes_list"].apply(
        lambda codes: [
            identifiers_by_name.get(name, "") for name in codes if identifiers_by_name.get(name, "")
        ]
    )
    dataframe["codes"] = dataframe["codes_list"].apply(separator.join)
    dataframe["code_ids"] = dataframe["code_ids_list"].apply(separator.join)
    dataframe["num_codes"] = dataframe["codes_list"].apply(len)
    dataframe["has_multi_label"] = dataframe["num_codes"] > 1
    dataframe.drop(columns=["codes_list", "code_ids_list"], inplace=True)
    return dataframe
