"""Inspect release artifacts for forbidden secret/database strings and hash them."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

FORBIDDEN = (
    # Database drivers/models must not be present in the distributed client.
    b"pymongo", b"motor", b"beanie", b"openoutreach.mongodb",
    # Server-only configuration and credential markers.
    b"MONGODB_URI", b"MONGODB_NAME", b"SECRET_KEY", b"JWT_SECRET_KEY",
    b"DAEMON_JWT_PRIVATE_KEY", b"LLM_API_KEY", b"RESEND_API_KEY",
    b"SMTP_PASSWORD", b"provider_key", b"password_encrypted",
)


def inspect_bytes(data: bytes) -> dict[str, object]:
    """Return non-secret artifact evidence without returning artifact bytes."""
    lowered = data.lower()
    matches = [value.decode("ascii") for value in FORBIDDEN if value.lower() in lowered]
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "forbidden_markers": matches}


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a desktop artifact")
    parser.add_argument("artifact", type=Path)
    args = parser.parse_args()
    report = {"artifact": args.artifact.name, **inspect_bytes(args.artifact.read_bytes())}
    print(json.dumps(report, sort_keys=True))
    return 2 if report["forbidden_markers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
