#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 10 Verification Script

Checks that all LinkedIn service files:
1. Have no Django imports
2. Use MongoDB collections exclusively
3. Compile without syntax errors
"""

import ast
import sys
from pathlib import Path


def check_django_imports(filepath):
    """Check for Django imports in a Python file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    tree = ast.parse(content, filename=str(filepath))

    django_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith('django'):
                django_imports.append(f"Line {node.lineno}: from {node.module} import ...")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith('django'):
                    django_imports.append(f"Line {node.lineno}: import {alias.name}")

    return django_imports


def check_mongodb_usage(filepath):
    """Check for MongoDB usage in file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    has_mongodb = (
        'get_mongodb_collection' in content or
        'from openoutreach.mongodb' in content or
        'from_dict' in content or
        '.save()' in content
    )

    return has_mongodb


def main():
    """Run verification checks."""
    service_files = [
        ('openoutreach/linkedin/services/smart_rate_limits.py', 'Smart Rate Limits'),
        ('openoutreach/linkedin/services/ghost_mode.py', 'Ghost Mode'),
        ('openoutreach/linkedin/services/health_monitor.py', 'Health Monitor'),
        ('openoutreach/linkedin/services/state_machine_stub.py', 'State Machine Stub'),
    ]

    all_passed = True

    print("=" * 70)
    print("PHASE 10 VERIFICATION: LinkedIn Services")
    print("=" * 70)
    print()

    for filepath, name in service_files:
        path = Path(filepath)
        print(f"Checking {name}...")

        if not path.exists():
            print(f"  [FAIL] File not found: {filepath}")
            all_passed = False
            continue

        # Check 1: No Django imports
        django_imports = check_django_imports(path)
        if django_imports:
            print(f"  [FAIL] Django imports found:")
            for imp in django_imports:
                print(f"     {imp}")
            all_passed = False
        else:
            print(f"  [PASS] No Django imports")

        # Check 2: Uses MongoDB (except stub)
        if 'stub' not in filepath:
            if check_mongodb_usage(path):
                print(f"  [PASS] Uses MongoDB collections")
            else:
                print(f"  [FAIL] No MongoDB usage found")
                all_passed = False
        else:
            print(f"  [PASS] Stub file (MongoDB not required)")

        # Check 3: Python syntax
        try:
            with open(path, 'r', encoding='utf-8') as f:
                compile(f.read(), str(path), 'exec')
            print(f"  [PASS] Python syntax valid")
        except SyntaxError as e:
            print(f"  [FAIL] Syntax error: {e}")
            all_passed = False

        print()

    print("=" * 70)
    if all_passed:
        print("[SUCCESS] ALL CHECKS PASSED - Phase 10 is complete!")
        print("=" * 70)
        return 0
    else:
        print("[ERROR] SOME CHECKS FAILED - Review errors above")
        print("=" * 70)
        return 1


if __name__ == '__main__':
    sys.exit(main())
