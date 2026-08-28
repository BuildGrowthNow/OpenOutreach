"""Inspect release artifacts for forbidden secret/database strings and hash them."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

FORBIDDEN = (b"MONGODB_URI", b"SECRET_KEY", b"LLM_API_KEY", b"provider_key", b"password_encrypted")


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a desktop artifact")
    parser.add_argument("artifact", type=Path)
    args = parser.parse_args()
    data = args.artifact.read_bytes()
    matches = [value.decode("ascii") for value in FORBIDDEN if value.lower() in data.lower()]
    report = {"artifact": args.artifact.name, "bytes": len(data),
              "sha256": hashlib.sha256(data).hexdigest(), "forbidden_markers": matches}
    print(json.dumps(report, sort_keys=True))
    return 2 if matches else 0


if __name__ == "__main__":
    raise SystemExit(main())
