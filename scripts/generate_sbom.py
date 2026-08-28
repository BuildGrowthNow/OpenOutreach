"""Generate a dependency SBOM without reading application secrets."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate CycloneDX-style Python SBOM")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = subprocess.run([sys.executable, "-m", "pip", "list", "--format=json"],
                            check=True, capture_output=True, text=True)
    packages = json.loads(result.stdout)
    document = {"bomFormat": "CycloneDX", "specVersion": "1.5",
                "metadata": {"timestamp": datetime.now(timezone.utc).isoformat()},
                "components": [{"type": "library", "name": p["name"], "version": p["version"]}
                               for p in packages]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
