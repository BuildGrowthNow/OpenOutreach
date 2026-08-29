#!/usr/bin/env python3
"""Build script for Lengrowth desktop app.

Usage:
    python desktop/build.py                  # Build for current platform
    python desktop/build.py --dmg            # Build + create macOS DMG
    python desktop/build.py --msix           # Build + create Windows MSIX
    python desktop/build.py --installer      # Build + create Windows installer (NSIS)
    python desktop/build.py --all            # Build all available formats
    python desktop/build.py --clean          # Clean build artifacts only
    python desktop/build.py --icons          # Regenerate icons only
    python desktop/build.py --sign           # Sign the app (macOS/Windows)
    python desktop/build.py --notarize       # Notarize macOS app (requires Apple Developer)

Environment:
    APPLE_DEVELOPER_ID      Apple Developer ID for signing (e.g., "Developer ID Application: Name (TEAMID)")
    APPLE_TEAM_ID           Apple Team ID for notarization
    APPLE_ID                Apple ID email for notarization
    APPLE_APP_PASSWORD      App-specific password for notarization
    SIGN_CERT_PATH          Path to Windows code signing certificate (optional)
    SIGN_CERT_PASS          Windows certificate password (optional)
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
BUILD_DIR = PROJECT_ROOT / "desktop" / "build"
DIST_DIR = PROJECT_ROOT / "desktop" / "dist"
ASSETS_DIR = PROJECT_ROOT / "openoutreach" / "desktop" / "assets"
MACOS_DIR = PROJECT_ROOT / "desktop" / "macos"


def get_version() -> str:
    """Read version from source."""
    version_file = PROJECT_ROOT / "openoutreach" / "desktop" / "__version__.py"
    if version_file.exists():
        with open(version_file) as f:
            for line in f:
                if line.startswith("__version__"):
                    return line.split("=")[1].strip().strip("\"'")
    return "2.1.2"


def clean():
    """Clean build artifacts."""
    print("Cleaning build artifacts...")
    shutil.rmtree(BUILD_DIR, ignore_errors=True)
    shutil.rmtree(DIST_DIR, ignore_errors=True)
    print("  Cleaned.")


def generate_icons():
    """Regenerate all icon formats."""
    print("Generating icons...")
    icon_script = ASSETS_DIR / "generate_icon.py"
    if not icon_script.exists():
        print(f"  Error: {icon_script} not found")
        return False

    result = subprocess.run(
        [sys.executable, str(icon_script)],
        cwd=str(ASSETS_DIR),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  Error: {result.stderr}")
        return False
    print("  Icons generated.")
    return True


def check_prerequisites() -> bool:
    """Check if build prerequisites are met."""
    print("Checking prerequisites...")

    # Check PyInstaller
    try:
        import PyInstaller
        print(f"  PyInstaller {PyInstaller.__version__}")
    except ImportError:
        print("  Error: PyInstaller not installed. Run: pip install pyinstaller")
        return False

    # Check Pillow (for icons)
    try:
        import PIL
        print(f"  Pillow {PIL.__version__}")
    except ImportError:
        print("  Error: Pillow not installed. Run: pip install Pillow")
        return False

    # Check required icons exist
    required_icons = ["icon.png"]
    if sys.platform == "win32":
        required_icons.append("icon.ico")

    for icon in required_icons:
        if not (ASSETS_DIR / icon).exists():
            print(f"  Warning: {icon} not found, generating icons...")
            generate_icons()
            break

    return True


def build() -> bool:
    """Run PyInstaller build."""
    print(f"\nBuilding Lengrowth v{get_version()} for {sys.platform}...")

    if not check_prerequisites():
        return False

    clean()

    spec_file = PROJECT_ROOT / "desktop" / "openoutreach.spec"
    if not spec_file.exists():
        print(f"Error: {spec_file} not found")
        return False

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--clean",
            "--noconfirm",
            "--workpath",
            str(BUILD_DIR),
            "--distpath",
            str(DIST_DIR),
            str(spec_file),
        ],
        cwd=str(PROJECT_ROOT),
    )

    if result.returncode != 0:
        print("Build failed!")
        return False

    # Verify output
    if sys.platform == "darwin":
        output = DIST_DIR / "Lengrowth.app"
    else:
        output = DIST_DIR / "Lengrowth.exe"

    if not output.exists():
        print(f"Error: Expected output not found: {output}")
        return False

    size_mb = sum(f.stat().st_size for f in output.rglob("*") if f.is_file()) / (1024 * 1024)
    print(f"\nBuild complete: {output}")
    print(f"Size: {size_mb:.1f} MB")
    return True


def create_dmg() -> bool:
    """Create macOS .dmg installer."""
    if sys.platform != "darwin":
        print("DMG creation only supported on macOS")
        return False

    print("\nCreating DMG...")

    app_path = DIST_DIR / "Lengrowth.app"
    if not app_path.exists():
        print(f"Error: {app_path} not found. Run build first.")
        return False

    dmg_path = DIST_DIR / f"Lengrowth-{get_version()}.dmg"
    if dmg_path.exists():
        dmg_path.unlink()

    # Try create-dmg first (better looking), fall back to hdiutil
    try:
        result = subprocess.run(
            [
                "create-dmg",
                "--volname", "Lengrowth",
                "--volicon", str(ASSETS_DIR / "icon.icns"),
                "--window-pos", "200", "120",
                "--window-size", "600", "400",
                "--icon-size", "100",
                "--icon", "Lengrowth.app", "150", "200",
                "--hide-extension", "Lengrowth.app",
                "--app-drop-link", "450", "200",
                "--no-internet-enable",
                str(dmg_path),
                str(app_path),
            ],
            check=True,
            capture_output=True,
        )
        print(f"DMG created: {dmg_path}")
        return True
    except FileNotFoundError:
        print("  create-dmg not found, using hdiutil...")
    except subprocess.CalledProcessError as e:
        print(f"  create-dmg failed: {e.stderr.decode() if e.stderr else str(e)}")
        print("  Falling back to hdiutil...")

    # Fallback to hdiutil
    result = subprocess.run(
        [
            "hdiutil", "create",
            "-volname", "Lengrowth",
            "-srcfolder", str(app_path),
            "-ov",
            "-format", "UDZO",
            str(dmg_path),
        ],
    )

    if result.returncode != 0:
        print("DMG creation failed!")
        return False

    print(f"DMG created: {dmg_path}")
    return True


def sign_macos_app() -> bool:
    """Sign macOS app with Developer ID certificate.

    Requires APPLE_DEVELOPER_ID environment variable.
    Example: "Developer ID Application: Your Name (TEAMID)"
    """
    if sys.platform != "darwin":
        print("macOS signing only supported on macOS")
        return False

    developer_id = os.environ.get("APPLE_DEVELOPER_ID")
    if not developer_id:
        print("Warning: APPLE_DEVELOPER_ID not set, skipping code signing.")
        print("  Set APPLE_DEVELOPER_ID to sign the app (e.g., 'Developer ID Application: Name (TEAMID)')")
        return False

    print(f"\nSigning app with: {developer_id}")

    app_path = DIST_DIR / "Lengrowth.app"
    if not app_path.exists():
        print(f"Error: {app_path} not found. Run build first.")
        return False

    entitlements = MACOS_DIR / "entitlements.plist"
    if not entitlements.exists():
        print(f"Error: {entitlements} not found.")
        return False

    # Sign all nested frameworks and dylibs first, then the app
    result = subprocess.run(
        [
            "codesign",
            "--deep",
            "--force",
            "--verify",
            "--verbose",
            "--options", "runtime",
            "--entitlements", str(entitlements),
            "--sign", developer_id,
            str(app_path),
        ],
    )

    if result.returncode != 0:
        print("Code signing failed!")
        return False

    # Verify signature
    verify_result = subprocess.run(
        ["codesign", "--verify", "--deep", "--strict", str(app_path)],
        capture_output=True,
    )

    if verify_result.returncode != 0:
        print(f"Signature verification failed: {verify_result.stderr.decode()}")
        return False

    print("App signed successfully!")
    return True


def notarize_macos_app() -> bool:
    """Notarize macOS app with Apple.

    Requires:
    - APPLE_TEAM_ID: Your Apple Team ID
    - APPLE_ID: Your Apple ID email
    - APPLE_APP_PASSWORD: App-specific password
    """
    if sys.platform != "darwin":
        print("Notarization only supported on macOS")
        return False

    team_id = os.environ.get("APPLE_TEAM_ID")
    apple_id = os.environ.get("APPLE_ID")
    app_password = os.environ.get("APPLE_APP_PASSWORD")

    if not all([team_id, apple_id, app_password]):
        print("Warning: Apple notarization credentials not set, skipping.")
        print("  Set APPLE_TEAM_ID, APPLE_ID, and APPLE_APP_PASSWORD")
        return False

    dmg_path = None
    for f in DIST_DIR.glob("Lengrowth-*.dmg"):
        dmg_path = f
        break

    if not dmg_path:
        print("Error: No DMG found. Create DMG first.")
        return False

    print(f"\nSubmitting for notarization: {dmg_path}")

    # Submit for notarization
    result = subprocess.run(
        [
            "xcrun", "notarytool", "submit",
            str(dmg_path),
            "--apple-id", apple_id,
            "--password", app_password,
            "--team-id", team_id,
            "--wait",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"Notarization failed: {result.stderr}")
        return False

    print("Notarization successful!")

    # Staple the ticket to the DMG
    print("Stapling notarization ticket...")
    staple_result = subprocess.run(
        ["xcrun", "stapler", "staple", str(dmg_path)],
    )

    if staple_result.returncode != 0:
        print("Warning: Stapling failed, but notarization succeeded.")
        return True

    print(f"Notarized and stapled: {dmg_path}")
    return True


def create_msix() -> bool:
    """Create Windows MSIX package for Microsoft Store."""
    if sys.platform != "win32":
        print("MSIX creation only supported on Windows")
        return False

    print("\nCreating MSIX package...")

    exe_path = DIST_DIR / "Lengrowth.exe"
    if not exe_path.exists():
        print(f"Error: {exe_path} not found. Run build first.")
        return False

    # Check for Windows SDK makeappx
    makeappx_paths = [
        Path(r"C:\Program Files (x86)\Windows Kits\10\bin\10.0.22000.0\x64\makeappx.exe"),
        Path(r"C:\Program Files (x86)\Windows Kits\10\bin\10.0.19041.0\x64\makeappx.exe"),
        Path(r"C:\Program Files (x86)\Windows Kits\10\bin\10.0.18362.0\x64\makeappx.exe"),
    ]

    makeappx = None
    for path in makeappx_paths:
        if path.exists():
            makeappx = path
            break

    if not makeappx:
        print("Error: Windows SDK (makeappx.exe) not found.")
        print("Install Windows SDK from: https://developer.microsoft.com/windows/downloads/windows-sdk/")
        return False

    # Create package directory structure
    pkg_dir = BUILD_DIR / "msix"
    shutil.rmtree(pkg_dir, ignore_errors=True)
    pkg_dir.mkdir(parents=True)

    # Copy executable
    shutil.copy2(exe_path, pkg_dir / "Lengrowth.exe")

    # Copy assets for MSIX
    assets_msix = pkg_dir / "Assets"
    assets_msix.mkdir()

    # Create required MSIX assets from our icons
    from PIL import Image

    icon_src = ASSETS_DIR / "icon.png"
    if icon_src.exists():
        icon = Image.open(icon_src)
        for size, name in [
            (44, "Square44x44Logo.png"),
            (150, "Square150x150Logo.png"),
            (310, "Wide310x150Logo.png"),
        ]:
            resized = icon.resize((size, size if "Wide" not in name else size // 2), Image.Resampling.LANCZOS)
            if "Wide" in name:
                wide = Image.new("RGBA", (310, 150), (0, 0, 0, 0))
                wide.paste(resized, ((310 - size) // 2, 0))
                wide.save(assets_msix / name)
            else:
                resized.save(assets_msix / name)

    # Create AppxManifest.xml
    version = get_version()
    version_parts = version.split(".")
    while len(version_parts) < 4:
        version_parts.append("0")
    msix_version = ".".join(version_parts[:4])

    manifest = f'''<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
         xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"
         xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities">

  <Identity Name="io.lengrowth.outreach"
            Publisher="CN=Lengrowth"
            Version="{msix_version}"
            ProcessorArchitecture="x64" />

  <Properties>
    <DisplayName>Lengrowth Outreach</DisplayName>
    <PublisherDisplayName>Lengrowth Outreach</PublisherDisplayName>
    <Description>B2B outreach automation for LinkedIn and WhatsApp</Description>
    <Logo>Assets\\Square150x150Logo.png</Logo>
  </Properties>

  <Resources>
    <Resource Language="en-us" />
  </Resources>

  <Dependencies>
    <TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.17763.0" MaxVersionTested="10.0.22000.0" />
  </Dependencies>

  <Capabilities>
    <Capability Name="internetClient" />
    <rescap:Capability Name="runFullTrust" />
  </Capabilities>

  <Applications>
    <Application Id="Lengrowth"
                 Executable="Lengrowth.exe"
                 EntryPoint="Windows.FullTrustApplication">
      <uap:VisualElements DisplayName="Lengrowth"
                          Description="Outreach automation"
                          BackgroundColor="#22c55e"
                          Square150x150Logo="Assets\\Square150x150Logo.png"
                          Square44x44Logo="Assets\\Square44x44Logo.png">
        <uap:DefaultTile Wide310x150Logo="Assets\\Wide310x150Logo.png" />
      </uap:VisualElements>
      <Extensions>
        <uap:Extension Category="windows.protocol">
          <uap:Protocol Name="lengrowth">
            <uap:DisplayName>Lengrowth Auth</uap:DisplayName>
          </uap:Protocol>
        </uap:Extension>
      </Extensions>
    </Application>
  </Applications>
</Package>
'''
    (pkg_dir / "AppxManifest.xml").write_text(manifest)

    # Create MSIX
    msix_path = DIST_DIR / f"Lengrowth-{version}.msix"
    result = subprocess.run(
        [str(makeappx), "pack", "/d", str(pkg_dir), "/p", str(msix_path), "/o"],
    )

    if result.returncode != 0:
        print("MSIX creation failed!")
        return False

    print(f"MSIX created: {msix_path}")
    print("\nNote: For Microsoft Store submission, you'll need to sign the MSIX with a trusted certificate.")
    return True


def create_nsis_installer() -> bool:
    """Create Windows NSIS installer for direct download."""
    if sys.platform != "win32":
        print("NSIS installer creation only supported on Windows")
        return False

    print("\nCreating NSIS installer...")

    exe_path = DIST_DIR / "Lengrowth.exe"
    if not exe_path.exists():
        print(f"Error: {exe_path} not found. Run build first.")
        return False

    # Check for NSIS
    nsis_paths = [
        Path(r"C:\Program Files (x86)\NSIS\makensis.exe"),
        Path(r"C:\Program Files\NSIS\makensis.exe"),
        # Chocolatey installs here on GitHub Actions runners
        Path(r"C:\ProgramData\chocolatey\bin\makensis.exe"),
        Path(r"C:\tools\nsis\makensis.exe"),
    ]

    makensis = None
    for path in nsis_paths:
        if path.exists():
            makensis = path
            break

    # Fall back to PATH lookup (covers choco shims and manual installs)
    if not makensis:
        makensis_on_path = shutil.which("makensis")
        if makensis_on_path:
            makensis = Path(makensis_on_path)

    if not makensis:
        print("Warning: NSIS not found. Skipping installer creation.")
        print("Install NSIS from: https://nsis.sourceforge.io/")
        return False

    version = get_version()

    # Create NSIS script
    nsi_script = BUILD_DIR / "installer.nsi"
    nsi_script.parent.mkdir(parents=True, exist_ok=True)

    eula_path = ASSETS_DIR / "eula.txt"

    nsi_content = f'''!include "MUI2.nsh"

Name "Lengrowth Outreach"
OutFile "{DIST_DIR}\\Lengrowth-{version}-Setup.exe"
; Install to per-user AppData so no UAC is needed (same as VS Code / Slack)
InstallDir "$LOCALAPPDATA\\Programs\\Lengrowth Outreach"
InstallDirRegKey HKCU "Software\\Lengrowth Outreach" "InstallDir"
RequestExecutionLevel user

!define MUI_ICON "{ASSETS_DIR}\\icon.ico"
!define MUI_UNICON "{ASSETS_DIR}\\icon.ico"
!define MUI_ABORTWARNING

; Welcome page
!define MUI_WELCOMEPAGE_TITLE "Welcome to Lengrowth Outreach {version}"
!define MUI_WELCOMEPAGE_TEXT "Fill your calendar with qualified meetings.$\\r$\\n$\\r$\\nDefine your ideal customer once. Lengrowth finds them on LinkedIn and WhatsApp, writes a unique message for each, and follows up until they're ready to talk - completely hands-off.$\\r$\\n$\\r$\\nThis wizard will guide you through the installation. Click Next to continue."

; Finish page
!define MUI_FINISHPAGE_RUN "$INSTDIR\\Lengrowth.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Launch Lengrowth Outreach now"
!define MUI_FINISHPAGE_TITLE "Installation Complete"
!define MUI_FINISHPAGE_TEXT "Lengrowth Outreach has been installed successfully.$\\r$\\n$\\r$\\nClick Finish to exit the installer."

!insertmacro MUI_PAGE_WELCOME
!define MUI_LICENSEPAGE_TEXT_TOP "Please review the End User License Agreement before installing Lengrowth Outreach."
!insertmacro MUI_PAGE_LICENSE "{eula_path}"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

Section "Install"
    ; Kill any running instance before replacing the exe
    nsExec::ExecToStack 'taskkill /F /IM Lengrowth.exe'
    Pop $0
    Sleep 1000

    ; Force-remove the install directory so no old exe lingers
    RMDir /r "$INSTDIR"

    SetOutPath "$INSTDIR"
    File "{exe_path}"

    ; Create start menu shortcuts (per-user)
    CreateDirectory "$SMPROGRAMS\\Lengrowth Outreach"
    CreateShortCut "$SMPROGRAMS\\Lengrowth Outreach\\Lengrowth Outreach.lnk" "$INSTDIR\\Lengrowth.exe"
    CreateShortCut "$SMPROGRAMS\\Lengrowth Outreach\\Uninstall.lnk" "$INSTDIR\\Uninstall.exe"

    ; Create desktop shortcut
    CreateShortCut "$DESKTOP\\Lengrowth Outreach.lnk" "$INSTDIR\\Lengrowth.exe"

    ; Register lengrowth:// protocol handler (per-user, no UAC)
    WriteRegStr HKCU "Software\\Classes\\lengrowth" "" "URL:Lengrowth Protocol"
    WriteRegStr HKCU "Software\\Classes\\lengrowth" "URL Protocol" ""
    WriteRegStr HKCU "Software\\Classes\\lengrowth\\shell\\open\\command" "" '"$INSTDIR\\Lengrowth.exe" "%1"'

    ; Write uninstall info to per-user registry (shows in Apps & Features)
    WriteRegStr HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\LengrowthOutreach" "DisplayName" "Lengrowth Outreach"
    WriteRegStr HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\LengrowthOutreach" "UninstallString" '"$INSTDIR\\Uninstall.exe"'
    WriteRegStr HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\LengrowthOutreach" "DisplayVersion" "{version}"
    WriteRegStr HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\LengrowthOutreach" "Publisher" "Lengrowth Outreach"
    WriteRegStr HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\LengrowthOutreach" "DisplayIcon" "$INSTDIR\\Lengrowth.exe"
    WriteRegStr HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\LengrowthOutreach" "URLInfoAbout" "https://lengrowth.com"
    WriteRegDWORD HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\LengrowthOutreach" "NoModify" 1
    WriteRegDWORD HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\LengrowthOutreach" "NoRepair" 1

    WriteUninstaller "$INSTDIR\\Uninstall.exe"
SectionEnd

Section "Uninstall"
    Delete "$INSTDIR\\Lengrowth.exe"
    Delete "$INSTDIR\\Uninstall.exe"
    RMDir "$INSTDIR"

    Delete "$SMPROGRAMS\\Lengrowth Outreach\\Lengrowth Outreach.lnk"
    Delete "$SMPROGRAMS\\Lengrowth Outreach\\Uninstall.lnk"
    RMDir "$SMPROGRAMS\\Lengrowth Outreach"
    Delete "$DESKTOP\\Lengrowth Outreach.lnk"

    DeleteRegKey HKCU "Software\\Classes\\lengrowth"
    DeleteRegKey HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\LengrowthOutreach"
    DeleteRegKey HKCU "Software\\Lengrowth Outreach"
SectionEnd
'''
    nsi_script.write_text(nsi_content)

    result = subprocess.run([str(makensis), str(nsi_script)])

    if result.returncode != 0:
        print("NSIS installer creation failed!")
        return False

    installer_path = DIST_DIR / f"Lengrowth-{version}-Setup.exe"
    print(f"Installer created: {installer_path}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Build Lengrowth desktop app")
    parser.add_argument("--dmg", action="store_true", help="Create macOS DMG")
    parser.add_argument("--msix", action="store_true", help="Create Windows MSIX")
    parser.add_argument("--installer", action="store_true", help="Create Windows NSIS installer")
    parser.add_argument("--all", action="store_true", help="Create all available formats")
    parser.add_argument("--clean", action="store_true", help="Clean build artifacts only")
    parser.add_argument("--icons", action="store_true", help="Regenerate icons only")
    parser.add_argument("--no-build", action="store_true", help="Skip build step (use existing)")
    parser.add_argument("--sign", action="store_true", help="Sign the app (macOS only, requires APPLE_DEVELOPER_ID)")
    parser.add_argument("--notarize", action="store_true", help="Notarize macOS app (requires Apple Developer credentials)")
    args = parser.parse_args()

    if args.clean:
        clean()
        return

    if args.icons:
        generate_icons()
        return

    # Build unless skipped
    if not args.no_build:
        if not build():
            sys.exit(1)

    # Code signing (macOS)
    if args.sign and sys.platform == "darwin":
        sign_macos_app()

    # Platform-specific packaging
    if args.all:
        if sys.platform == "darwin":
            if args.sign:
                sign_macos_app()
            create_dmg()
            if args.notarize:
                notarize_macos_app()
        elif sys.platform == "win32":
            create_msix()
            create_nsis_installer()
    else:
        if args.dmg:
            create_dmg()
        if args.msix:
            create_msix()
        if args.installer:
            create_nsis_installer()
        if args.notarize:
            notarize_macos_app()

    print("\nBuild process complete!")


if __name__ == "__main__":
    main()
