"""Injected translation prompting, parsing, routing, and fallback behavior."""

import json
import logging
import re
import time
from collections.abc import Callable, Sequence
from typing import Protocol

import pandas as pd

from codeframe.config import LanguageConfig, ModelConfig
from codeframe.exceptions import TranslationUnresolvedError
from codeframe.language import LANGUAGE_NAME_BY_CODE

logger = logging.getLogger(__name__)

type Messages = list[dict[str, str]]


class ChatCompletion(Protocol):
    """Injected Chat Completions boundary used by translation."""

    def __call__(
        self,
        *,
        model: str,
        messages: Messages,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Return the assistant message content."""


class BatchTranslator(Protocol):
    """Callable boundary used by translation routing and fallback."""

    def __call__(
        self,
        texts: Sequence[str],
        *,
        source_language_name: str | None,
        target_language_name: str,
    ) -> list[str]:
        """Translate a batch while preserving order."""


def translate_batch(
    complete: ChatCompletion,
    texts: Sequence[str],
    *,
    source_language_name: str | None = None,
    target_language_name: str = "French",
    model: str = "gpt-4.1-mini",
) -> list[str]:
    """Translate one ordered batch using the notebook's exact prompt contract."""

    numbered = "\n".join(f"[{index + 1}] {text}" for index, text in enumerate(texts))
    source_hint = (
        None
        if not source_language_name
        or source_language_name.strip().lower() in {"other", "unknown", "auto"}
        else source_language_name.strip()
    )
    if source_hint:
        prompt = (
            f"Translate the following {len(texts)} survey responses "
            f"from {source_hint.upper()} to {target_language_name.upper()}.\n\n"
            f"{numbered}\n\n"
            f"Return ONLY a JSON array with exactly {len(texts)} strings, "
            'preserving order. Example: ["translation 1", "translation 2"]'
        )
    else:
        prompt = (
            f"Translate the following {len(texts)} survey responses "
            f"into {target_language_name.upper()}. Detect each response's source "
            f"language automatically. If a response is already in "
            f"{target_language_name.upper()}, return it unchanged.\n\n"
            f"{numbered}\n\n"
            f"Return ONLY a JSON array with exactly {len(texts)} strings, "
            'preserving order. Example: ["translation 1", "translation 2"]'
        )

    content = complete(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (f"Translate to {target_language_name}. Return only a JSON array."),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=min(4000, len(texts) * 120),
    )
    raw = re.sub(r"^```(?:json)?\n?", "", content.strip())
    raw = re.sub(r"\n?```$", "", raw)
    result = json.loads(raw)
    if not isinstance(result, list) or len(result) != len(texts):
        raise ValueError(f"Expected {len(texts)} translations, got {len(result)}")
    return [str(translated).strip() for translated in result]


def resolve_translate_source_codes(
    source_language_codes: Sequence[str] | str | None,
    *,
    config: LanguageConfig,
    target_language_code: str,
) -> list[str] | None:
    """Resolve explicit or configured source codes; ``None`` means all non-target."""

    codes: Sequence[str] | str | None
    if source_language_codes is None:
        codes = config.translate_source_language_codes
    else:
        codes = source_language_codes
    if codes is None:
        return None
    if isinstance(codes, str):
        codes = [codes]
    target = target_language_code.lower().strip()
    return [
        normalized
        for code in codes
        if (normalized := str(code).lower().strip()) and normalized != target
    ]


def _translate_index_batches(
    dataframe: pd.DataFrame,
    translator: BatchTranslator,
    index_list: list[object],
    *,
    text_column: str,
    output_column: str,
    status_column: str,
    source_language_name: str | None,
    target_language_name: str,
    batch_size: int,
    delay: float,
    sleep: Callable[[float], None],
) -> None:
    """Translate selected indexes with batch parsing and per-item fallback."""

    count = len(index_list)
    if count == 0:
        return
    label = source_language_name or "auto-detected"
    unresolved: list[object] = []
    for start in range(0, count, batch_size):
        batch_indexes = index_list[start : start + batch_size]
        batch_texts = [str(value) for value in dataframe.loc[batch_indexes, text_column]]
        try:
            translated = translator(
                batch_texts,
                source_language_name=source_language_name,
                target_language_name=target_language_name,
            )
            if len(translated) != len(batch_indexes):
                raise ValueError(
                    f"Expected {len(batch_indexes)} translations, got {len(translated)}"
                )
            for index, translated_text in zip(batch_indexes, translated, strict=True):
                dataframe.at[index, output_column] = translated_text
                dataframe.at[index, status_column] = "translated"
        except (RuntimeError, KeyboardInterrupt, SystemExit):
            raise
        except Exception as batch_error:
            logger.warning(
                "Batch parse failed for %s (%s); retrying %s responses individually",
                label,
                type(batch_error).__name__,
                len(batch_indexes),
            )
            for index in batch_indexes:
                try:
                    translated = translator(
                        [str(dataframe.at[index, text_column])],
                        source_language_name=source_language_name,
                        target_language_name=target_language_name,
                    )
                    if len(translated) != 1:
                        raise ValueError(f"Expected 1 translations, got {len(translated)}")
                    dataframe.at[index, output_column] = translated[0]
                    dataframe.at[index, status_column] = "translated"
                except (RuntimeError, KeyboardInterrupt, SystemExit):
                    raise
                except Exception as item_error:
                    dataframe.at[index, status_column] = "unresolved_translation"
                    unresolved.append(index)
                    logger.error(
                        "Translation failed for response index %s (%s)",
                        index,
                        type(item_error).__name__,
                    )
            if unresolved:
                raise TranslationUnresolvedError(
                    f"Translation unresolved for response index(es): {unresolved}"
                ) from batch_error
        sleep(delay)


def translate_source_records(
    dataframe: pd.DataFrame,
    translator: BatchTranslator,
    *,
    language_config: LanguageConfig | None = None,
    source_language_codes: Sequence[str] | str | None = None,
    target_language_code: str | None = None,
    text_column: str = "cleaned_text",
    output_column: str | None = None,
    status_column: str = "translation_status",
    batch_size: int | None = None,
    delay: float = 0.3,
    sleep: Callable[[float], None] = time.sleep,
) -> pd.DataFrame:
    """Translate selected non-target records while preserving notebook statuses."""

    config = language_config or LanguageConfig()
    target_code = (target_language_code or config.target_language_code).lower().strip()
    resolved_output_column = output_column or f"final_text_{target_code}"
    resolved_batch_size = config.translation_batch_size if batch_size is None else batch_size
    if resolved_batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    if delay < 0:
        raise ValueError("delay must not be negative")
    target_name = LANGUAGE_NAME_BY_CODE.get(target_code, target_code)
    codes = resolve_translate_source_codes(
        source_language_codes,
        config=config,
        target_language_code=target_code,
    )

    dataframe[resolved_output_column] = dataframe[text_column]
    dataframe[status_column] = "not_requested"
    if "detected_lang" not in dataframe.columns:
        raise KeyError("Column 'detected_lang' is required. Run preprocess_data() first.")

    normalized_languages = dataframe["detected_lang"].astype(str).str.lower()
    if codes is None:
        translate_mask = normalized_languages.ne(target_code)
    else:
        translate_mask = normalized_languages.isin(set(codes))
    indexes_to_translate = dataframe.index[translate_mask].tolist()
    target_mask = normalized_languages.eq(target_code)
    dataframe.loc[target_mask, status_column] = "not_required"
    dataframe.loc[indexes_to_translate, status_column] = "pending"
    if not indexes_to_translate:
        return dataframe

    grouped: dict[tuple[str, str | None], list[object]] = {}
    for index in indexes_to_translate:
        language_code = str(dataframe.at[index, "detected_lang"]).lower().strip()
        detection_status = (
            str(dataframe.at[index, "detected_lang_status"]).lower().strip()
            if "detected_lang_status" in dataframe.columns
            else "detected"
        )
        source_name = (
            LANGUAGE_NAME_BY_CODE.get(language_code) if detection_status == "detected" else None
        )
        grouped.setdefault((language_code, source_name), []).append(index)

    for (_, source_name), indexes in sorted(
        grouped.items(),
        key=lambda item: (-len(item[1]), item[0][0], item[0][1] or ""),
    ):
        _translate_index_batches(
            dataframe,
            translator,
            indexes,
            text_column=text_column,
            output_column=resolved_output_column,
            status_column=status_column,
            source_language_name=source_name,
            target_language_name=target_name,
            batch_size=resolved_batch_size,
            delay=delay,
            sleep=sleep,
        )
    return dataframe


def make_batch_translator(
    complete: ChatCompletion,
    *,
    model_config: ModelConfig | None = None,
) -> BatchTranslator:
    """Bind an injected completion function to the configured coding model."""

    model = (model_config or ModelConfig()).coding_model

    def bound(
        texts: Sequence[str],
        *,
        source_language_name: str | None,
        target_language_name: str,
    ) -> list[str]:
        return translate_batch(
            complete,
            texts,
            source_language_name=source_language_name,
            target_language_name=target_language_name,
            model=model,
        )

    return bound
