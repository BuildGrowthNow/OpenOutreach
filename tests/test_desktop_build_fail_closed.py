from pathlib import Path


BUILD = Path(__file__).parents[1] / "desktop" / "build.py"
SIGN = Path(__file__).parents[1] / "desktop" / "windows" / "sign.ps1"
RELEASE_SIGN = Path(__file__).parents[1] / "desktop" / "windows" / "sign_release.ps1"


def test_requested_packaging_operations_check_failure_results():
    source = BUILD.read_text(encoding="utf-8")
    assert "if not create_msix():" in source
    assert "if not create_nsis_installer():" in source
    assert "if not create_dmg():" in source
    assert "if not notarize_macos_app():" in source
    assert "if sys.platform != \"darwin\" or not sign_macos_app():" in source


def test_windows_signing_verification_is_fail_closed_and_timestamp_is_tls():
    source = SIGN.read_text(encoding="utf-8")
    assert 'Timestamp = "https://timestamp.digicert.com"' in source
    assert "Get-ChildItem -LiteralPath $sdkRoot -Filter signtool.exe" in source
    assert "& $signTool sign" in source
    assert "& $signTool verify" in source
    assert 'Write-Host "Error: Signature verification failed"' in source
    assert 'Write-Host "Warning: Signature verification failed"' not in source
    assert "exit 1" in source


def test_approved_release_workflow_requires_signing_gates():
    workflow = (Path(__file__).parents[1] / ".github" / "workflows" / "desktop-build.yml").read_text(encoding="utf-8")
    assert "Sign Windows release artifacts for approved publish" in workflow
    assert "Sign macOS app for approved publish" in workflow
    assert "Notarize macOS DMG for approved publish" in workflow
    windows = workflow.split("  build-windows:", 1)[1].split("  release:", 1)[0]
    assert windows.index("- name: Get version") < windows.index("- name: Sign Windows release artifacts for approved publish")
    assert windows.index("- name: Sign Windows release artifacts for approved publish") < windows.index("- name: Upload Windows exe artifact")
    script = RELEASE_SIGN.read_text(encoding="utf-8")
    assert "WINDOWS_SIGNING_CERT_BASE64" in script
    assert "Signature verification failed" in script
    assert "Remove-Item -LiteralPath $certificatePath" in script
