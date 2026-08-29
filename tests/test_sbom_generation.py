import json
from pathlib import Path

from scripts import generate_sbom


def test_sbom_generation_writes_cyclonedx_components(monkeypatch, tmp_path: Path):
    class Result:
        stdout = '[{"name": "Example-Package", "version": "1.2.3"}]'

    monkeypatch.setattr(generate_sbom.subprocess, "run", lambda *args, **kwargs: Result())
    output = tmp_path / "SBOM.cyclonedx.json"
    monkeypatch.setattr(
        generate_sbom.sys,
        "argv",
        ["generate_sbom.py", "--output", str(output)],
    )

    assert generate_sbom.main() == 0
    document = json.loads(output.read_text(encoding="utf-8"))
    assert document["bomFormat"] == "CycloneDX"
    assert document["specVersion"] == "1.5"
    assert document["components"] == [
        {"name": "Example-Package", "type": "library", "version": "1.2.3"}
    ]
    assert document["metadata"]["timestamp"]
