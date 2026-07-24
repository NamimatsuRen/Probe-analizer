from __future__ import annotations

import ast
from pathlib import Path


def test_domain_and_analysis_do_not_import_gui_packages() -> None:
    source_root = Path(__file__).parents[2] / "src" / "probe_app"
    forbidden = ("PySide6", "pyqtgraph")
    violations: list[str] = []

    for package_name in ("domain", "analysis"):
        for path in sorted((source_root / package_name).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                imported_modules = _imported_modules(node)
                for module in imported_modules:
                    if module.startswith(forbidden):
                        relative_path = path.relative_to(source_root)
                        violations.append(f"{relative_path}: {module}")

    assert violations == []


def _imported_modules(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)
    if isinstance(node, ast.ImportFrom) and node.module is not None:
        return (node.module,)
    return ()
