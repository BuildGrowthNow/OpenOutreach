#!/usr/bin/env python3
"""Test script for desktop app components.

Tests configuration, auth, protocol handler, icon loading, and version.
Run from project root: python desktop/test_app.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_version():
    """Test version is accessible from multiple paths."""
    print("Testing version...")

    from openoutreach.desktop.__version__ import __version__ as v1
    from openoutreach.desktop import __version__ as v2

    print(f"  Version: {v1}")
    assert v1 == v2, "Version mismatch between __version__.py and __init__.py"
    assert v1, "Version should not be empty"
    print("  OK")


def test_config():
    """Test config loading and saving."""
    from openoutreach.desktop.config import AppConfig

    print("Testing config...")
    config = AppConfig.load()
    print(f"  API URL: {config.api_url}")

    original_url = config.api_url

    # Save and reload
    config.api_url = "https://test.example.com"
    config.save()
    config2 = AppConfig.load()
    assert config2.api_url == "https://test.example.com"

    # Restore original
    config.api_url = original_url
    config.save()
    print("  OK")


def test_auth():
    """Test auth manager interface (does not store in keychain)."""
    print("Testing auth...")

    try:
        from openoutreach.desktop.auth import AuthManager
    except ImportError as e:
        print(f"  Skipped (keyring not installed): {e}")
        return

    from openoutreach.desktop.config import AppConfig

    config = AppConfig.load()
    auth = AuthManager(config)

    assert hasattr(auth, "is_logged_in")
    assert hasattr(auth, "get_token")
    assert hasattr(auth, "get_profile_id")
    assert hasattr(auth, "login")
    assert hasattr(auth, "logout")
    print("  OK")


def test_protocol_handler():
    """Test URL protocol parsing."""
    from openoutreach.desktop.protocol_handler import parse_auth_callback

    print("Testing protocol handler...")

    # Valid URL
    result = parse_auth_callback("openoutreach://auth?token=abc123&profile_id=xyz789")
    assert result is not None
    assert result["token"] == "abc123"
    assert result["profile_id"] == "xyz789"

    # Invalid URLs
    assert parse_auth_callback("https://example.com") is None
    assert parse_auth_callback("openoutreach://wrong") is None
    assert parse_auth_callback("openoutreach://auth") is None
    assert parse_auth_callback("openoutreach://auth?token=abc") is None

    print("  OK")


def test_icon():
    """Test icon files exist and load correctly."""
    print("Testing icons...")

    assets_dir = PROJECT_ROOT / "openoutreach" / "desktop" / "assets"
    required_icons = ["icon.png", "icon.ico"]

    for icon_name in required_icons:
        icon_path = assets_dir / icon_name
        if not icon_path.exists():
            print(f"  Warning: {icon_name} not found")
            continue

        try:
            from PIL import Image

            img = Image.open(icon_path)
            print(f"  {icon_name}: {img.size[0]}x{img.size[1]}")
        except ImportError:
            print("  Warning: Pillow not installed, skipping icon load test")
            break

    print("  OK")


def test_imports():
    """Test all module imports work."""
    print("Testing imports...")

    modules = [
        "openoutreach.desktop",
        "openoutreach.desktop.__version__",
        "openoutreach.desktop.app",
        "openoutreach.desktop.config",
        "openoutreach.desktop.auth",
        "openoutreach.desktop.protocol_handler",
        "openoutreach.desktop.updater",
    ]

    for module in modules:
        try:
            __import__(module)
            print(f"  {module.split('.')[-1]}")
        except ImportError as e:
            print(f"  Warning: {module}: {e}")

    print("  OK")


def test_updater():
    """Test updater module."""
    print("Testing updater...")

    from openoutreach.desktop.updater import check_for_updates, prompt_update

    assert callable(check_for_updates)
    assert callable(prompt_update)
    print("  OK")


def test_browser_detect():
    """Test browser detection."""
    print("Testing browser detection...")

    from openoutreach.core.browser_detect import detect_browsers, get_preferred_browser

    browsers = detect_browsers()
    print(f"  Detected {len(browsers)} browser(s)")

    for browser in browsers:
        print(f"    - {browser.name}: {browser.path}")

    preferred = get_preferred_browser()
    if preferred:
        print(f"  Preferred: {preferred.name}")
    else:
        print("  Warning: No supported browser found")

    print("  OK")


def main():
    """Run all tests."""
    print("OpenOutreach Desktop App - Component Tests\n")
    print(f"Project root: {PROJECT_ROOT}\n")

    tests = [
        test_version,
        test_imports,
        test_config,
        test_auth,
        test_protocol_handler,
        test_icon,
        test_updater,
        test_browser_detect,
    ]

    failed = []
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"  FAILED: {e}")
            failed.append(test.__name__)

    print()
    if failed:
        print(f"FAILED: {', '.join(failed)}")
        sys.exit(1)
    else:
        print("All tests passed")


if __name__ == "__main__":
    main()
