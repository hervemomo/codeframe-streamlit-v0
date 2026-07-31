"""Notebook-baseline checks used by tests, pre-commit, and CI."""

from hashlib import sha256
from pathlib import Path

from codeframe.exceptions import NotebookParityError

NOTEBOOK_RELATIVE_PATH = Path("original_notebook.ipynb")
EXPECTED_NOTEBOOK_SHA256 = "202eefa5db6c0f39d72e63f1401e1c30edc821e83326483c92c1721b72c626f8"


def notebook_sha256(path: Path) -> str:
    """Return the exact SHA-256 digest of a notebook file."""

    digest = sha256()
    with path.open("rb") as notebook:
        for chunk in iter(lambda: notebook.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_notebook_baseline(repository_root: Path) -> str:
    """Verify that the source notebook is byte-identical to the Phase 1 baseline."""

    notebook_path = repository_root / NOTEBOOK_RELATIVE_PATH
    if not notebook_path.is_file():
        raise NotebookParityError(f"Notebook baseline file is missing: {notebook_path}")
    actual = notebook_sha256(notebook_path)
    if actual != EXPECTED_NOTEBOOK_SHA256:
        raise NotebookParityError(
            f"Notebook baseline mismatch: expected {EXPECTED_NOTEBOOK_SHA256}, received {actual}"
        )
    return actual
