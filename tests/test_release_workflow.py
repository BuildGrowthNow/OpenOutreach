from pathlib import Path

import yaml

from openoutreach.desktop.__version__ import __version__


WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "desktop-build.yml"


def test_desktop_version_is_bumped_for_release():
    assert tuple(int(part) for part in __version__.split(".")) >= (2, 1, 5)


def test_release_requires_explicit_manual_publish_input():
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    # PyYAML's YAML 1.1 loader treats the GitHub Actions `on` key as boolean.
    trigger = workflow.get("on", workflow.get(True))
    assert trigger["workflow_dispatch"]["inputs"]["publish"]["default"] is False
    assert "workflow_dispatch" in workflow["jobs"]["release"]["if"]
    assert "inputs.publish" in workflow["jobs"]["release"]["if"]
    assert workflow["permissions"]["contents"] == "read"


def test_push_to_main_publishes_desktop_release():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    trigger = yaml.safe_load(workflow).get("on", yaml.safe_load(workflow).get(True))

    assert ".github/workflows/desktop-build.yml" in trigger["push"]["paths"]
    release_job = workflow.split("  release:", 1)[1].split("    runs-on:", 1)[0]
    assert "github.event_name == 'push'" in release_job
    assert "inputs.publish == true" in release_job


def test_windows_installer_build_is_fail_closed():
    text = WORKFLOW.read_text(encoding="utf-8")
    installer_step = text.split("- name: Install NSIS and create installer", 1)[1].split(
        "- name: Get version", 1
    )[0]
    assert "continue-on-error" not in installer_step
    rename_step = text.split("- name: Rename installer for stable download URL", 1)[1].split(
        "- name: Upload Windows installer artifact", 1
    )[0]
    assert "|| true" not in rename_step
    upload_step = text.split("- name: Upload Windows installer artifact", 1)[1].split(
        "  release:", 1
    )[0]
    assert "if: hashFiles" not in upload_step
    assert "Download Windows installer artifact\n        uses:" in text
    assert "name: Lengrowth-Windows-MSIX-${{ steps.version.outputs.version }}" in text
    assert "Download Windows MSIX artifact" in text
    assert "./release/windows/Lengrowth-${{ steps.version.outputs.version }}.msix" in text


def test_release_keeps_legacy_updater_bootstrap_aliases():
    text = WORKFLOW.read_text(encoding="utf-8")
    evidence = text.split("- name: Inspect artifacts and generate release evidence", 1)[1].split(
        "- name: Create release on Lengrowth/outbound", 1
    )[0]

    assert "cp ./release/macos/Lengrowth-macOS.dmg ./release/macos/OpenOutreach-${{ steps.version.outputs.version }}.dmg" in evidence
    assert "cp ./release/windows/Lengrowth.exe ./release/windows/OpenOutreach-${{ steps.version.outputs.version }}-Setup.exe" in evidence
    assert "sha256sum ./release/macos/OpenOutreach-${{ steps.version.outputs.version }}.dmg" in evidence
    assert "sha256sum ./release/windows/OpenOutreach-${{ steps.version.outputs.version }}-Setup.exe" in evidence
    assert "./release/macos/OpenOutreach-${{ steps.version.outputs.version }}.dmg" in text
    assert "./release/windows/OpenOutreach-${{ steps.version.outputs.version }}-Setup.exe" in text
