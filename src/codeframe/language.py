"""Lingua language detection with notebook-equivalent status routing."""

from functools import lru_cache
from typing import Any, Protocol

from lingua import Language, LanguageDetectorBuilder

from codeframe.config import LanguageConfig

LANGUAGE_NAME_BY_CODE: dict[str, str] = {
    "en": "English",
    "fr": "French",
    "es": "Spanish",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "ar": "Arabic",
}

LINGUA_LANGUAGES = (
    Language.ENGLISH,
    Language.FRENCH,
    Language.SPANISH,
    Language.GERMAN,
    Language.ITALIAN,
    Language.PORTUGUESE,
    Language.DUTCH,
    Language.ARABIC,
)


class LanguageDetector(Protocol):
    """Subset of Lingua's detector API required by the domain service."""

    def compute_language_confidence_values(self, text: str) -> list[Any]:
        """Return descending language confidence values."""


@lru_cache(maxsize=1)
def build_language_detector() -> LanguageDetector:
    """Build the configured Lingua detector lazily and cache it."""

    return LanguageDetectorBuilder.from_languages(*LINGUA_LANGUAGES).build()


def count_alphabetic_characters(text: str) -> int:
    """Count Unicode alphabetic characters."""

    return sum(1 for character in text if character.isalpha())


def detect_language(
    text: object,
    *,
    config: LanguageConfig | None = None,
    detector: LanguageDetector | None = None,
) -> tuple[str, str, float | None]:
    """Return ``(ISO code, status, confidence)`` using notebook precedence."""

    resolved_config = config or LanguageConfig()
    normalized_text = "" if text is None else str(text)
    if count_alphabetic_characters(normalized_text) < resolved_config.minimum_alpha_characters:
        return "other", "insufficient_text", None

    active_detector = detector or build_language_detector()
    values = active_detector.compute_language_confidence_values(normalized_text)
    if not values or values[0].value <= 0.0:
        return "other", "unsupported_language", None

    top = values[0]
    language_code = str(top.language.iso_code_639_1.name).lower()
    top_confidence = float(top.value)
    if (
        len(values) > 1
        and top_confidence - float(values[1].value) < resolved_config.mixed_language_margin
    ):
        return language_code, "mixed_language", top_confidence
    if top_confidence < resolved_config.uncertain_threshold:
        return language_code, "uncertain", top_confidence
    return language_code, "detected", top_confidence
