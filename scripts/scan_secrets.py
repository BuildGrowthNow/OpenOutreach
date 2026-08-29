"""Scan tracked text files for high-confidence embedded credentials.

The scanner intentionally reports only rule names and paths. It is a release
guardrail, not a replacement for an external security review or secret
manager. Example/config documentation files may contain placeholders, so they
are excluded from this high-confidence scan.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path


_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    (
        "credentialed-database-url",
        re.compile(r"\b(?:mongodb(?:\+srv)?|postgres(?:ql)?|mysql)://[^{}\s\"']+:[^{}\s\"']+@"),
    ),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{20,}\b")),
    (
        "assigned-secret",
        re.compile(
            r"\b(?:api[_-]?key|access[_-]?token|secret[_-]?key|private[_-]?key|password)"
            r"\s*[:=]\s*[\"'][^\"'\r\n]{20,}[\"']",
            re.IGNORECASE,
        ),
    ),
)

_EXCLUDED_NAMES = {".env.example", ".env.template"}
_EXCLUDED_SUFFIXES = {".md", ".rst", ".txt"}
_EXCLUDED_PARTS = {"tests"}


def scan_text(text: str) -> list[str]:
    """Return matching rule names without returning matched secret material."""
    # Comments commonly document URI shapes; they are not embedded values.
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    return [name for name, pattern in _RULES if pattern.search(code)]


def tracked_paths() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], check=True, capture_output=True
    )
    return [Path(value) for value in result.stdout.decode("utf-8").split("\0") if value]


def scan_path(path: Path) -> list[str]:
    if (
        path.name in _EXCLUDED_NAMES
        or path.suffix.lower() in _EXCLUDED_SUFFIXES
        or any(part in _EXCLUDED_PARTS for part in path.parts)
    ):
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    return scan_text(text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", action="append", type=Path, help="Tracked file or directory to scan")
    args = parser.parse_args()

    paths = args.path or tracked_paths()
    findings: list[tuple[Path, str]] = []
    for path in paths:
        if path.is_dir():
            candidates = [candidate for candidate in path.rglob("*") if candidate.is_file()]
        else:
            candidates = [path]
        for candidate in candidates:
            for rule in scan_path(candidate):
                findings.append((candidate, rule))

    if findings:
        for path, rule in findings:
            print(f"SECRET FINDING: {rule}: {path}")
        return 1
    print(f"Secret scan passed: {len(paths)} tracked path(s) inspected; no high-confidence findings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
