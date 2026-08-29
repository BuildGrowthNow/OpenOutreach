"""Regression checks for exception-safe production logging."""

from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "openoutreach"
LOG_LEVELS = {"debug", "info", "warning", "error", "exception", "critical"}
EXCEPTION_NAMES = {"e", "e2", "exc", "exception"}
def _is_raw_exception_argument(node: ast.AST) -> bool:
    """Return whether an expression passes the caught exception itself."""
    if isinstance(node, ast.Name):
        return node.id in EXCEPTION_NAMES
    if isinstance(node, ast.JoinedStr):
        return any(
            isinstance(child, ast.FormattedValue)
            and isinstance(child.value, ast.Name)
            and child.value.id in EXCEPTION_NAMES
            for child in node.values
        )
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return node.func.id in {"str", "repr"} and any(
            isinstance(argument, ast.Name) and argument.id in EXCEPTION_NAMES
            for argument in node.args
        )
    return False


def test_logger_calls_do_not_interpolate_exception_objects() -> None:
    violations: list[str] = []

    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute):
                continue
            if not isinstance(node.func.value, ast.Name) or node.func.value.id != "logger":
                continue
            if node.func.attr not in LOG_LEVELS:
                continue
            if any(_is_raw_exception_argument(argument) for argument in node.args):
                relative = path.relative_to(PROJECT_ROOT).as_posix()
                violations.append(f"{relative}:{node.lineno}")

    assert not violations, "logger call interpolates an exception object: " + ", ".join(violations)
