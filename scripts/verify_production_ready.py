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
from pathlib import Path


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
        return False, str(e)


def check_django_imports() -> bool:
    """Verify zero Django imports in codebase."""
    print("\n1. Checking for Django imports...")

    # Check "from django" imports
    success, output = run_command(
        ["grep", "-r", "from django", "openoutreach", "--include=*.py"],
        "Checking 'from django' imports"
    )

    # grep returns 1 when no matches found (which is what we want)
    if success or "No such file" in output:
        print("   [FAIL] Found 'from django' imports!")
        print(f"   {output[:500]}")
        return False

    # Check "import django" imports
    success, output = run_command(
        ["grep", "-r", "import django", "openoutreach", "--include=*.py"],
        "Checking 'import django' imports"
    )

    if success or "No such file" in output:
        print("   [FAIL] Found 'import django' imports!")
        print(f"   {output[:500]}")
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
            ["python", "-c", import_stmt],
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
        ["pip", "show", "django"],
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
        ["pytest", "tests/integration/test_daemon_smoke.py::TestDaemonSmoke", "-v", "--tb=short"],
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


def main():
    """Run all verification checks."""
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
    ]

    results = {}

    for name, check_func in checks:
        try:
            results[name] = check_func()
        except Exception as e:
            print(f"\n   [FAIL] Check failed with exception: {e}")
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
        print("\nALL CHECKS PASSED - PRODUCTION READY")
        print("\nNext steps:")
        print("  1. Set up MongoDB connection (Atlas or local)")
        print("  2. Run full integration tests with MongoDB")
        print("  3. Test daemon: python -m openoutreach.cli rundaemon")
        print("  4. Test API: python -m openoutreach.cli runserver")
        print("  5. Deploy to production")
        print("\nSee PHASE_14_COMPLETE.md for detailed instructions.")
        return 0
    else:
        print("\n[FAIL] SOME CHECKS FAILED - NOT PRODUCTION READY")
        print("\nPlease fix the failing checks before deploying.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
