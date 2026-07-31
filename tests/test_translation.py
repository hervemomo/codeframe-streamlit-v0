"""Mocked translation prompt, parsing, routing, and fallback tests."""

import json
from collections.abc import Sequence
from typing import Any

import pandas as pd
import pytest

from codeframe.config import LanguageConfig, ModelConfig
from codeframe.exceptions import TranslationUnresolvedError
from codeframe.translation import (
    make_batch_translator,
    resolve_translate_source_codes,
    translate_batch,
    translate_source_records,
)


@pytest.mark.unit
def test_translate_batch_builds_source_hint_prompt_and_parses_fence() -> None:
    request: dict[str, Any] = {}

    def complete(**kwargs: Any) -> str:
        request.update(kwargs)
        return '```json\n["Bonjour", "Bon prix"]\n```'

    result = translate_batch(
        complete,
        ["Hello", "Good price"],
        source_language_name="English",
        target_language_name="French",
        model="mock-model",
    )

    assert result == ["Bonjour", "Bon prix"]
    assert request["model"] == "mock-model"
    assert request["temperature"] == 0.1
    assert request["max_tokens"] == 240
    prompt = request["messages"][1]["content"]
    assert "from ENGLISH to FRENCH" in prompt
    assert "[1] Hello\n[2] Good price" in prompt


@pytest.mark.unit
def test_translate_batch_auto_detect_prompt_and_shape_validation() -> None:
    prompts: list[str] = []

    def complete(**kwargs: Any) -> str:
        prompts.append(kwargs["messages"][1]["content"])
        return json.dumps(["Bonjour"])

    assert translate_batch(
        complete,
        ["Hello"],
        source_language_name=None,
        target_language_name="French",
    ) == ["Bonjour"]
    assert "Detect each response's source language automatically" in prompts[0]

    with pytest.raises(ValueError, match="Expected 2 translations, got 1"):
        translate_batch(
            complete,
            ["one", "two"],
            target_language_name="French",
        )


@pytest.mark.unit
def test_source_code_resolution_uses_config_and_removes_target() -> None:
    config = LanguageConfig(
        target_language_code="fr",
        translate_source_language_codes=("EN", "fr", " es "),
    )

    assert resolve_translate_source_codes(None, config=config, target_language_code="fr") == [
        "en",
        "es",
    ]
    assert (
        resolve_translate_source_codes(
            None,
            config=LanguageConfig(),
            target_language_code="fr",
        )
        is None
    )


@pytest.mark.unit
def test_invalid_routing_configuration_fails_before_translation() -> None:
    dataframe = pd.DataFrame(
        {
            "cleaned_text": ["hello"],
            "detected_lang": ["en"],
            "detected_lang_status": ["detected"],
        }
    )
    with pytest.raises(ValueError, match="batch_size"):
        translate_source_records(
            dataframe,
            lambda texts, **_: list(texts),
            batch_size=0,
            sleep=lambda _: None,
        )
    with pytest.raises(ValueError, match="delay"):
        translate_source_records(
            dataframe,
            lambda texts, **_: list(texts),
            delay=-1,
            sleep=lambda _: None,
        )


@pytest.mark.parity
def test_translation_routes_confident_and_uncertain_groups() -> None:
    dataframe = pd.DataFrame(
        {
            "cleaned_text": ["bonjour", "hello", "uncertain english", "hola"],
            "detected_lang": ["fr", "en", "en", "es"],
            "detected_lang_status": [
                "detected",
                "detected",
                "uncertain",
                "detected",
            ],
        }
    )
    calls: list[tuple[list[str], str | None, str]] = []

    def translator(
        texts: Sequence[str],
        *,
        source_language_name: str | None,
        target_language_name: str,
    ) -> list[str]:
        calls.append((list(texts), source_language_name, target_language_name))
        return [f"fr:{text}" for text in texts]

    translated = translate_source_records(
        dataframe,
        translator,
        delay=0,
        sleep=lambda _: None,
    )

    assert translated["translation_status"].tolist() == [
        "not_required",
        "translated",
        "translated",
        "translated",
    ]
    assert translated["final_text_fr"].tolist() == [
        "bonjour",
        "fr:hello",
        "fr:uncertain english",
        "fr:hola",
    ]
    assert calls == [
        (["uncertain english"], None, "French"),
        (["hello"], "English", "French"),
        (["hola"], "Spanish", "French"),
    ]


@pytest.mark.unit
def test_restricted_translation_leaves_other_languages_not_requested() -> None:
    dataframe = pd.DataFrame(
        {
            "cleaned_text": ["bonjour", "hello", "hola"],
            "detected_lang": ["fr", "en", "es"],
            "detected_lang_status": ["detected", "detected", "detected"],
        }
    )

    result = translate_source_records(
        dataframe,
        lambda texts, **_: [f"fr:{text}" for text in texts],
        source_language_codes=["en"],
        delay=0,
        sleep=lambda _: None,
    )

    assert result["translation_status"].tolist() == [
        "not_required",
        "translated",
        "not_requested",
    ]
    assert result["final_text_fr"].tolist() == [
        "bonjour",
        "fr:hello",
        "hola",
    ]


@pytest.mark.integration
def test_batch_parse_failure_retries_only_items_in_that_batch() -> None:
    dataframe = pd.DataFrame(
        {
            "cleaned_text": ["one", "two"],
            "detected_lang": ["en", "en"],
            "detected_lang_status": ["detected", "detected"],
        }
    )
    batch_sizes: list[int] = []

    def translator(
        texts: Sequence[str],
        *,
        source_language_name: str | None,
        target_language_name: str,
    ) -> list[str]:
        batch_sizes.append(len(texts))
        if len(texts) > 1:
            raise ValueError("bad batch JSON")
        return [f"fr:{texts[0]}"]

    result = translate_source_records(
        dataframe,
        translator,
        batch_size=2,
        delay=0,
        sleep=lambda _: None,
    )

    assert batch_sizes == [2, 1, 1]
    assert result["final_text_fr"].tolist() == ["fr:one", "fr:two"]


@pytest.mark.unit
def test_unresolved_and_fatal_translation_fail_closed() -> None:
    dataframe = pd.DataFrame(
        {
            "cleaned_text": ["one"],
            "detected_lang": ["en"],
            "detected_lang_status": ["detected"],
        }
    )

    def unresolved(*_: Any, **__: Any) -> list[str]:
        raise ValueError("invalid response")

    with pytest.raises(TranslationUnresolvedError, match=r"\[0\]"):
        translate_source_records(
            dataframe.copy(),
            unresolved,
            delay=0,
            sleep=lambda _: None,
        )

    def fatal(*_: Any, **__: Any) -> list[str]:
        raise RuntimeError("quota")

    with pytest.raises(RuntimeError, match="quota"):
        translate_source_records(
            dataframe.copy(),
            fatal,
            delay=0,
            sleep=lambda _: None,
        )


@pytest.mark.unit
def test_bound_translator_uses_configured_coding_model() -> None:
    observed: list[str] = []

    def complete(**kwargs: Any) -> str:
        observed.append(kwargs["model"])
        return '["bonjour"]'

    translator = make_batch_translator(
        complete, model_config=ModelConfig(coding_model="configured-model")
    )
    assert translator(
        ["hello"],
        source_language_name="English",
        target_language_name="French",
    ) == ["bonjour"]
    assert observed == ["configured-model"]
