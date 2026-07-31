"""Fail when the source notebook differs from the recorded Phase 1 baseline."""

from pathlib import Path

from codeframe.parity import verify_notebook_baseline


def main() -> int:
    """Run the immutable-notebook check from the repository root."""

    repository_root = Path(__file__).resolve().parents[1]
    digest = verify_notebook_baseline(repository_root)
    print(f"Notebook baseline verified: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
