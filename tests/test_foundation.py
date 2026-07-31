"""Phase 1 package, architecture, and notebook-baseline tests."""

from pathlib import Path

import pytest

import codeframe
from codeframe.exceptions import NotebookParityError
from codeframe.parity import (
    EXPECTED_NOTEBOOK_SHA256,
    NOTEBOOK_RELATIVE_PATH,
    notebook_sha256,
    verify_notebook_baseline,
)
from scripts.check_architecture import architecture_violations

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.unit
def test_package_imports_without_streamlit_side_effects() -> None:
    assert codeframe.__version__ == "0.1.0"


@pytest.mark.unit
def test_reusable_package_does_not_import_streamlit() -> None:
    assert architecture_violations(REPOSITORY_ROOT / "src" / "codeframe") == []


@pytest.mark.parity
def test_notebook_matches_phase_one_baseline() -> None:
    assert verify_notebook_baseline(REPOSITORY_ROOT) == EXPECTED_NOTEBOOK_SHA256
    assert notebook_sha256(REPOSITORY_ROOT / NOTEBOOK_RELATIVE_PATH) == (EXPECTED_NOTEBOOK_SHA256)


@pytest.mark.parity
def test_missing_notebook_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(NotebookParityError, match="missing"):
        verify_notebook_baseline(tmp_path)


@pytest.mark.parity
def test_changed_notebook_fails_closed(tmp_path: Path) -> None:
    notebook = tmp_path / NOTEBOOK_RELATIVE_PATH
    notebook.write_text("changed", encoding="utf-8")
    with pytest.raises(NotebookParityError, match="mismatch"):
        verify_notebook_baseline(tmp_path)
