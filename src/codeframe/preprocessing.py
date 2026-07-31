"""Notebook-equivalent cleaning, filtering, deduplication, and audit output."""

import html
import logging
import re
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import ftfy
import pandas as pd

from codeframe.config import LanguageConfig
from codeframe.language import detect_language

logger = logging.getLogger(__name__)

EMPTY_RESPONSES = {
    "n/a",
    "na",
    "none",
    "no",
    "yes",
    "idk",
    "dk",
    "dont know",
    "don't know",
    "nothing",
    "no comment",
    "no comments",
    "-",
    ".",
    "..",
    "...",
    "nil",
    "not applicable",
    "no answer",
    "no response",
    "blank",
    "skip",
    "skipped",
    "",
    "aucun",
    "aucune",
    "rien",
    "néant",
    "sans",
    "—",
    "d'accord",
    "ras",
    "r.a.s",
    "pas de commentaire",
    "aucun commentaire",
    "je ne sais pas",
    "je sais pas",
    "rien à signaler",
    "rien a signaler",
}
DEFAULT_MIN_WORDS = 2

URL_RE = re.compile(r"\bhttps?://[^\s<>]+|\bwww\.[^\s<>]+", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[\w.\-+]+@[\w.\-]+\.\w+\b", re.IGNORECASE)
HTML_TAG_RE = re.compile(r"<[^>]+>")
EMOJI_RE = re.compile(
    "[\U0001f600-\U0001f64f\U0001f300-\U0001f5ff\U0001f680-\U0001f6ff"
    "\U0001f700-\U0001f77f\U0001f780-\U0001f7ff\U0001f800-\U0001f8ff"
    "\U0001f900-\U0001f9ff\U0001fa00-\U0001fa6f\U0001fa70-\U0001faff"
    "\u2702-\u27b0\u24c2-\U0001f251\U0001f1e6-\U0001f1ff"
    "\u2600-\u26ff]|\ufe0f|\U0001f3fb|\U0001f3fc|\U0001f3fd"
    "|\U0001f3fe|\U0001f3ff",
    re.UNICODE,
)

type DetectionResult = tuple[str, str, float | None]
type Detector = Callable[[object], DetectionResult]


def clean_text(
    text: object,
    *,
    normalize_form: str = "NFC",
    remove_control_chars: bool = True,
    fix_entities: bool = True,
    replace_urls_with: str = "__URL__",
    replace_emails_with: str = "__EMAIL__",
    emoji_handling: str = "remove",
    emoji_token: str = "__EMOJI__",
    lowercase: bool = False,
    strip_accents: bool = False,
) -> str:
    """Sanitize a response using the exact notebook operation order."""

    try:
        is_missing = bool(pd.isna(cast(Any, text)))
    except Exception:
        is_missing = False
    if is_missing:
        return ""
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    text = html.unescape(text)
    text = ftfy.fix_text(
        text,
        normalization=normalize_form,
        remove_control_chars=remove_control_chars,
        fix_entities=fix_entities,
    )
    text = HTML_TAG_RE.sub(" ", text)
    text = URL_RE.sub(f" {replace_urls_with} " if replace_urls_with else " ", text)
    text = EMAIL_RE.sub(f" {replace_emails_with} " if replace_emails_with else " ", text)
    if emoji_handling == "token":
        text = EMOJI_RE.sub(f" {emoji_token} ", text)
    elif emoji_handling == "remove":
        text = EMOJI_RE.sub(" ", text)
    if lowercase:
        text = text.lower()
    if strip_accents:
        text = "".join(
            character
            for character in unicodedata.normalize("NFD", text)
            if unicodedata.category(character) != "Mn"
        )
    return re.sub(r"\s+", " ", text).strip()


def is_valid_response(text: object, min_words: int = DEFAULT_MIN_WORDS) -> bool:
    """Return whether a cleaned response is substantive enough to code."""

    if not text:
        return False
    normalized = str(text).strip()
    if not normalized or normalized.lower() in EMPTY_RESPONSES:
        return False
    if re.fullmatch(r"[\W_]+", normalized):
        return False
    if normalized.lower() in {"__url__", "__email__", "__emoji__"}:
        return False
    return len(normalized.split()) >= min_words


def partition_preprocessed_records(
    dataframe: pd.DataFrame,
    min_words: int = DEFAULT_MIN_WORDS,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return retained, invalid-audit, and exact-duplicate-audit records."""

    working = dataframe.copy()
    working["cleaned_text"] = working["original_text"].apply(clean_text)
    working["is_valid"] = working["cleaned_text"].apply(
        lambda value: is_valid_response(value, min_words)
    )
    working["is_duplicate"] = working.duplicated(subset=["cleaned_text"], keep="first")
    invalid = working[~working["is_valid"]].copy()
    duplicates = working[working["is_duplicate"]].copy()
    retained = working[working["is_valid"] & ~working["is_duplicate"]].copy()
    retained.drop(columns=["is_valid", "is_duplicate"], inplace=True)
    return retained, invalid, duplicates


def write_removed_records_audit(
    invalid: pd.DataFrame,
    duplicates: pd.DataFrame,
    *,
    output_dir: Path,
    filename: str = "removed_records.xlsx",
) -> Path | None:
    """Write the notebook's two-sheet audit when any removed records exist."""

    if len(invalid) + len(duplicates) == 0:
        return None
    output_dir.mkdir(parents=True, exist_ok=True)
    audit_path = output_dir / filename
    with pd.ExcelWriter(audit_path, engine="openpyxl") as writer:
        invalid.to_excel(writer, sheet_name="Invalid Records", index=False)
        duplicates.to_excel(writer, sheet_name="Duplicate Records", index=False)
    logger.info("Audit file saved -> %s", audit_path)
    return audit_path


def preprocess_data(
    dataframe: pd.DataFrame,
    *,
    output_dir: Path,
    min_words: int = DEFAULT_MIN_WORDS,
    audit_filename: str = "removed_records.xlsx",
    language_config: LanguageConfig | None = None,
    detector: Detector | None = None,
) -> pd.DataFrame:
    """Clean, filter, deduplicate, detect language, and write removal audit."""

    retained, invalid, duplicates = partition_preprocessed_records(dataframe, min_words=min_words)
    write_removed_records_audit(
        invalid,
        duplicates,
        output_dir=output_dir,
        filename=audit_filename,
    )
    removed_count = len(set(invalid.index).union(set(duplicates.index)))
    logger.info("Removed %s record(s). %s remaining.", removed_count, len(retained))

    resolved_config = language_config or LanguageConfig()
    detect = detector or (lambda value: detect_language(value, config=resolved_config))
    detection = retained["cleaned_text"].apply(detect)
    retained["detected_lang"] = detection.apply(lambda result: result[0])
    retained["detected_lang_status"] = detection.apply(lambda result: result[1])
    retained["detected_lang_confidence"] = detection.apply(lambda result: result[2])
    logger.info(
        "Language detection status counts: %s",
        retained["detected_lang_status"].value_counts().to_dict(),
    )
    return retained
