"""Standalone tabular exports with explicit destinations."""

import json
from pathlib import Path
from typing import Any

import pandas as pd

from codeframe.paths import ensure_output_dir


def save_preprocessed_csv(
    dataframe: pd.DataFrame,
    *,
    output_dir: Path,
    file_stem: str,
) -> Path:
    """Write the notebook-equivalent ``<stem>_processed.csv`` export."""

    destination = ensure_output_dir(output_dir) / f"{file_stem}_processed.csv"
    dataframe.to_csv(destination, index=False)
    return destination


def save_codebook_json(
    codebook: dict[str, Any],
    *,
    output_dir: Path,
    file_name: str,
) -> Path:
    """Write a UTF-8 codebook JSON file to an explicit destination."""

    destination = ensure_output_dir(output_dir) / file_name
    destination.write_text(
        json.dumps(codebook, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return destination
