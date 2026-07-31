"""Deterministic language-status tests using an injected detector."""

from types import SimpleNamespace
from typing import Any

import pytest

from codeframe.config import LanguageConfig
from codeframe.language import (
    build_language_detector,
    count_alphabetic_characters,
    detect_language,
)


class FakeDetector:
    """Return configured Lingua-shaped confidence objects."""

    def __init__(self, values: list[Any]) -> None:
        self.values = values
        self.calls = 0

    def compute_language_confidence_values(self, text: str) -> list[Any]:
        self.calls += 1
        return self.values


def confidence(code: str, value: float) -> Any:
    """Create the nested attributes exposed by Lingua."""

    language = SimpleNamespace(iso_code_639_1=SimpleNamespace(name=code.upper()))
    return SimpleNamespace(language=language, value=value)


@pytest.mark.unit
def test_alphabetic_count_is_unicode_aware() -> None:
    assert count_alphabetic_characters("é1-ع") == 2


@pytest.mark.unit
def test_insufficient_text_does_not_call_detector() -> None:
    detector = FakeDetector([confidence("fr", 0.99)])

    assert detect_language("123!", detector=detector) == (
        "other",
        "insufficient_text",
        None,
    )
    assert detector.calls == 0


@pytest.mark.unit
def test_unsupported_language_when_detector_has_no_positive_score() -> None:
    empty = FakeDetector([])
    zero = FakeDetector([confidence("fr", 0.0)])

    assert detect_language("texte", detector=empty) == (
        "other",
        "unsupported_language",
        None,
    )
    assert detect_language("texte", detector=zero) == (
        "other",
        "unsupported_language",
        None,
    )


@pytest.mark.parity
def test_mixed_status_precedes_uncertain_status() -> None:
    detector = FakeDetector([confidence("fr", 0.70), confidence("en", 0.67)])

    assert detect_language("mixed text", detector=detector) == (
        "fr",
        "mixed_language",
        0.70,
    )


@pytest.mark.unit
def test_uncertain_and_detected_thresholds() -> None:
    uncertain = FakeDetector([confidence("en", 0.79), confidence("fr", 0.20)])
    detected = FakeDetector([confidence("en", 0.80), confidence("fr", 0.10)])
    config = LanguageConfig(uncertain_threshold=0.80)

    assert detect_language("english text", detector=uncertain, config=config)[1] == ("uncertain")
    assert detect_language("english text", detector=detected, config=config) == (
        "en",
        "detected",
        0.80,
    )


@pytest.mark.integration
def test_configured_lingua_detector_supports_notebook_languages() -> None:
    detector = build_language_detector()

    french = detect_language(
        "Cette boisson est très rafraîchissante et agréable.",
        detector=detector,
    )
    english = detect_language(
        "This beverage has a refreshing and pleasant taste.",
        detector=detector,
    )

    assert french[0] == "fr"
    assert english[0] == "en"
    assert french[2] is not None
    assert english[2] is not None
