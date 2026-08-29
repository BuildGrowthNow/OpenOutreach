#!/usr/bin/env python3
"""
Production Readiness Verification Script

Verifies that the OpenOutreach platform is production-ready after
the Django → FastAPI + MongoDB migration.

Usage:
    python scripts/verify_production_ready.py
"""
import subprocess
import sys
import os
import re
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from pathlib import Path


_DJANGO_IMPORT = re.compile(r"^\s*(?:from|import)\s+django(?:\.|\s|$)", re.MULTILINE)


def run_command(cmd: list[str], description: str) -> tuple[bool, str]:
    """Run a command and return success status and output."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=Path(__file__).parent.parent
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, f"Command timed out: {' '.join(cmd)}"
    except Exception as e:
        return False, f"{type(e).__name__}: command execution failed"


def check_django_imports() -> bool:
    """Verify zero Django imports in codebase."""
    print("\n1. Checking for Django imports...")
    root = Path(__file__).parent.parent / "openoutreach"
    matches: list[str] = []
    for path in root.rglob("*.py"):
        if any(part == "__pycache__" for part in path.parts):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            print(f"   [FAIL] Could not read {path}: {type(exc).__name__}")
            return False
        if _DJANGO_IMPORT.search(content):
            matches.append(str(path.relative_to(root.parent)))

    if matches:
        print("   [FAIL] Found 'import django' imports!")
        print(f"   {', '.join(matches[:10])}")
        return False

    print("   [PASS] Zero Django imports found")
    return True


def check_module_imports() -> bool:
    """Verify critical modules can be imported."""
    print("\n2. Checking module imports...")

    imports_to_test = [
        "from openoutreach.mongodb.models import Lead, Deal, Task, Campaign; print('OK')",
        "from openoutreach.core.daemon import run_daemon; print('OK')",
        "from openoutreach.core.scheduler import plan_connect_window; print('OK')",
        "from openoutreach.linkedin.tasks.connect import handle_connect; print('OK')",
        "from openoutreach.api_v2.main import app; print('OK')",
    ]

    for import_stmt in imports_to_test:
        success, output = run_command(
            [sys.executable, "-c", import_stmt],
            f"Testing: {import_stmt}"
        )

        # Check if "OK" appears in output (import succeeded)
        if "OK" not in output:
            print(f"   [FAIL] Failed: {import_stmt.split(';')[0]}")
            print(f"   Error: {output[:200]}")
            return False

    print("   [PASS] All critical modules import successfully")
    return True


def check_django_uninstalled() -> bool:
    """Verify Django is not installed."""
    print("\n3. Checking Django installation status...")

    success, output = run_command(
        [sys.executable, "-m", "pip", "show", "django"],
        "Checking if Django is installed"
    )

    if success:
        print("   [WARN]  Django is still installed!")
        print("   Run: pip uninstall django -y")
        return False

    print("   [PASS] Django is not installed")
    return True


def check_smoke_tests() -> bool:
    """Run integration smoke tests."""
    print("\n4. Running smoke tests...")

    success, output = run_command(
        [sys.executable, "-m", "pytest", "tests/integration/test_daemon_smoke.py::TestDaemonSmoke", "-v", "--tb=short"],
        "Running daemon smoke tests"
    )

    if not success:
        print("   [FAIL] Smoke tests failed!")
        print(f"   {output[-500:]}")
        return False

    # Check for passing tests in output
    if "passed" not in output.lower():
        print("   [FAIL] No passing tests found")
        print(f"   {output[-500:]}")
        return False

    print("   [PASS] Smoke tests passed")
    return True


def check_pytest_config() -> bool:
    """Verify pytest.ini has no Django references."""
    print("\n5. Checking pytest configuration...")

    pytest_ini = Path(__file__).parent.parent / "pytest.ini"

    if not pytest_ini.exists():
        print("   [WARN]  pytest.ini not found")
        return False

    content = pytest_ini.read_text()

    if "DJANGO_SETTINGS_MODULE" in content:
        print("   [FAIL] pytest.ini still has DJANGO_SETTINGS_MODULE")
        return False

    if "--reuse-db" in content:
        print("   [FAIL] pytest.ini still has Django-specific --reuse-db flag")
        return False

    print("   [PASS] pytest.ini is Django-free")
    return True


def check_production_prerequisites() -> bool:
    """Require deployment prerequisites before calling the result production-ready."""
    print("\n6. Checking production deployment prerequisites...")
    required = {
        "application secret key": os.getenv("SECRET_KEY"),
        "independent JWT signing key": os.getenv("JWT_SECRET_KEY"),
        "independent cookie encryption key": os.getenv("COOKIE_ENCRYPTION_KEY"),
        "MongoDB URI": os.getenv("MONGODB_URI") or os.getenv("OPENOUTREACH_MONGODB_URI"),
        "MongoDB database name": os.getenv("MONGODB_NAME") or os.getenv("OPENOUTREACH_MONGODB_NAME"),
        "daemon JWT private key": os.getenv("DAEMON_JWT_PRIVATE_KEY") or os.getenv("DAEMON_JWT_PRIVATE_KEY_B64"),
        "daemon JWT public key": os.getenv("DAEMON_JWT_PUBLIC_KEY") or os.getenv("DAEMON_JWT_PUBLIC_KEY_B64"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        print("   [BLOCKED] Missing deployment-managed prerequisites: " + ", ".join(missing))
        print("   Local source/smoke checks are not evidence of production readiness.")
        return False
    print("   [PASS] Required deployment-managed prerequisites are configured")
    return True


def check_cloud_deployment(
    base_url: str,
    expected_version: str | None = None,
    expected_commit: str | None = None,
) -> bool:
    """Perform a read-only smoke/parity check against a deployed API."""
    print(f"\n7. Checking deployed cloud API ({base_url})...")
    base_url = base_url.rstrip("/")
    try:
        health_request = Request(f"{base_url}/api/health", method="GET")
        with urlopen(health_request, timeout=10) as response:
            health = json.loads(response.read())
            health_cache_control = response.headers.get("Cache-Control", "")

        if health.get("status") != "operational":
            print(f"   [FAIL] Cloud health status is {health.get('status')!r}")
            return False
        if health_cache_control.lower() != "no-store":
            print(f"   [FAIL] /api/health Cache-Control is {health_cache_control!r}, expected 'no-store'")
            return False

        openapi_request = Request(f"{base_url}/openapi.json", method="GET")
        with urlopen(openapi_request, timeout=10) as response:
            openapi = json.loads(response.read())

        compatibility_request = Request(
            f"{base_url}/api/daemon/v2/compatibility", method="GET"
        )
        with urlopen(compatibility_request, timeout=10) as response:
            compatibility = json.loads(response.read())
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
        print(f"   [FAIL] Cloud smoke check failed: {type(exc).__name__}")
        return False

    deployed_version = str(openapi.get("info", {}).get("version", ""))
    deployed_commit = str(health.get("build", {}).get("commit", ""))
    if not deployed_version or not deployed_commit:
        print(
            "   [FAIL] Cloud build identity is incomplete: "
            f"version={deployed_version or '<missing>'}, "
            f"commit={deployed_commit or '<missing>'}"
        )
        return False

    minimum_secure = str(compatibility.get("minimum_secure", ""))
    capabilities = compatibility.get("capabilities", [])
    required_capabilities = {"device-auth", "typed-events"}
    if not minimum_secure or not required_capabilities.issubset(set(capabilities)):
        print(
            "   [FAIL] Secure daemon compatibility contract is incomplete: "
            f"minimum_secure={minimum_secure or '<missing>'}, "
            f"capabilities={capabilities!r}"
        )
        return False

    print(
        "   [PASS] Cloud health is operational; deployed API build: "
        f"{deployed_version} ({deployed_commit}); secure daemon floor: {minimum_secure}"
    )
    if expected_version and deployed_version != expected_version:
        print(f"   [FAIL] Deployed API version {deployed_version!r} != expected {expected_version!r}")
        return False
    if expected_commit and deployed_commit != expected_commit:
        print(f"   [FAIL] Deployed API commit {deployed_commit!r} != expected {expected_commit!r}")
        return False
    return True


def check_frontend_deployment(base_url: str) -> bool:
    """Perform a read-only smoke check against the public frontend."""
    print(f"\n8. Checking deployed frontend ({base_url})...")
    try:
        request = Request(base_url.rstrip("/") + "/", method="GET")
        with urlopen(request, timeout=10) as response:
            status = getattr(response, "status", 200)
            body = response.read()
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        print(f"   [FAIL] Frontend smoke check failed: {type(exc).__name__}")
        return False

    if status != 200 or not body:
        print(f"   [FAIL] Frontend returned status={status} with content={bool(body)}")
        return False
    print(f"   [PASS] Frontend returned HTTP 200 with {len(body)} bytes")
    return True


def main():
    """Run all verification checks."""
    import argparse

    parser = argparse.ArgumentParser(description="Verify local and optionally deployed production readiness")
    parser.add_argument("--cloud-url", help="Base URL for a read-only deployed API smoke check")
    parser.add_argument("--expected-cloud-version", help="Expected OpenAPI version for --cloud-url")
    parser.add_argument("--expected-cloud-commit", help="Expected build commit exposed by --cloud-url")
    parser.add_argument("--frontend-url", help="Public frontend URL for a read-only smoke check")
    args = parser.parse_args()

    if args.cloud_url and not args.frontend_url:
        parser.error("--frontend-url is required when --cloud-url is supplied")

    print("=" * 70)
    print("OpenOutreach Production Readiness Verification")
    print("Django -> FastAPI + MongoDB Migration")
    print("=" * 70)

    checks = [
        ("Django Imports", check_django_imports),
        ("Module Imports", check_module_imports),
        ("Django Uninstalled", check_django_uninstalled),
        ("Pytest Config", check_pytest_config),
        ("Smoke Tests", check_smoke_tests),
        ("Production Prerequisites", check_production_prerequisites),
    ]
    if args.cloud_url:
        checks.append(
            (
                "Cloud Deployment",
                lambda: check_cloud_deployment(
                    args.cloud_url, args.expected_cloud_version, args.expected_cloud_commit
                ),
            )
        )
    if args.frontend_url:
        checks.append(("Frontend Deployment", lambda: check_frontend_deployment(args.frontend_url)))

    results = {}

    for name, check_func in checks:
        try:
            results[name] = check_func()
        except Exception as e:
            print(f"\n   [FAIL] Check failed with exception: {type(e).__name__}")
            results[name] = False

    # Summary
    print("\n" + "=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)

    all_passed = all(results.values())

    for name, passed in results.items():
        status = "[PASS] PASS" if passed else "[FAIL] FAIL"
        print(f"{status:12} {name}")

    print("=" * 70)

    if all_passed:
        print("\nALL CHECKS PASSED - LOCAL AND DEPLOYMENT PREREQUISITE CHECKS PASSED")
        print("Production readiness still requires live integration, channel validation, and deployment smoke evidence.")
        return 0
    else:
        print("\n[FAIL] SOME CHECKS FAILED - NOT PRODUCTION READY")
        print("\nPlease fix the failing checks before deploying.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
