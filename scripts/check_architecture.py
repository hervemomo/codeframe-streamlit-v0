"""Enforce the package dependency direction without importing application modules."""

import ast
from pathlib import Path

DISALLOWED_DOMAIN_IMPORTS = {"streamlit"}


def imported_roots(path: Path) -> set[str]:
    """Return the root names imported by one Python source file."""

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", maxsplit=1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", maxsplit=1)[0])
    return roots


def architecture_violations(source_root: Path) -> list[str]:
    """Return deterministic messages for forbidden domain imports."""

    violations: list[str] = []
    for path in sorted(source_root.rglob("*.py")):
        forbidden = sorted(imported_roots(path) & DISALLOWED_DOMAIN_IMPORTS)
        if forbidden:
            display_path = path.relative_to(source_root.parent.parent)
            violations.append(f"{display_path}: forbidden import(s): {', '.join(forbidden)}")
    return violations


def main() -> int:
    """Check every reusable package module."""

    repository_root = Path(__file__).resolve().parents[1]
    violations = architecture_violations(repository_root / "src" / "codeframe")
    if violations:
        print("\n".join(violations))
        return 1
    print("Architecture verified: reusable package has no Streamlit imports.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
