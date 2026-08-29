"""Audit a Lengrowth desktop log without printing its contents.

This is intentionally read-only. It reports metadata and aggregate matches so
an operator can decide whether a log needs authorized retention/revocation
handling without copying secrets into a terminal or support ticket.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


CALLBACK_TOKEN = re.compile(
    r"(?:lengrowth|openoutreach)://[^\s]*[?&](?:token|refresh_token)=",
    re.IGNORECASE,
)
SENSITIVE_MARKER = re.compile(
    r"\b(?:password|cookie|secret[_-]?key|api[_-]?key|authorization|bearer|refresh[_-]?token)\b",
    re.IGNORECASE,
)


def audit(path: Path) -> dict[str, object]:
    """Return aggregate findings for *path* without exposing line contents."""
    result: dict[str, object] = {
        "path": str(path),
        "exists": path.is_file(),
        "bytes": 0,
        "lines": 0,
        "callback_token_lines": 0,
        "sensitive_marker_lines": 0,
    }
    if not path.is_file():
        return result

    result["bytes"] = path.stat().st_size
    line_count = 0
    callback_token_lines = 0
    sensitive_marker_lines = 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line_count += 1
            if CALLBACK_TOKEN.search(line):
                callback_token_lines += 1
            if SENSITIVE_MARKER.search(line):
                sensitive_marker_lines += 1
    result["lines"] = line_count
    result["callback_token_lines"] = callback_token_lines
    result["sensitive_marker_lines"] = sensitive_marker_lines
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, required=True, help="Log path to audit")
    args = parser.parse_args()
    report = audit(args.path)
    print(json.dumps(report, sort_keys=True))
    return 1 if report["callback_token_lines"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
