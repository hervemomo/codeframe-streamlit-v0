"""Explicit output-directory handling shared by all file writers."""

from pathlib import Path


def ensure_output_dir(output_dir: Path) -> Path:
    """Create and return an explicit output directory."""

    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir
