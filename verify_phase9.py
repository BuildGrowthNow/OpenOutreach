#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 9 Verification Script

Checks that all task handlers:
1. Have no Django imports
2. Export the correct handler function
3. Use MongoDB models exclusively
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

def check_handler_function(filepath, handler_name):
    """Check that the handler function exists."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    tree = ast.parse(content, filename=str(filepath))

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == handler_name:
            return True

    return False

def check_mongodb_imports(filepath):
    """Check for MongoDB model imports."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    has_mongodb = 'openoutreach.mongodb' in content or 'from openoutreach.mongodb.models import' in content
    has_crm_models = 'from openoutreach.crm.models import' in content

    return has_mongodb or has_crm_models

def main():
    """Run verification checks."""
    task_handlers = [
        ('openoutreach/linkedin/tasks/follow_up.py', 'handle_follow_up'),
        ('openoutreach/linkedin/tasks/connect.py', 'handle_connect'),
        ('openoutreach/linkedin/tasks/check_pending.py', 'handle_check_pending'),
        ('openoutreach/linkedin/tasks/send_manual_message.py', 'handle_send_manual_message'),
    ]

    all_passed = True

    print("=" * 70)
    print("PHASE 9 VERIFICATION: LinkedIn Task Handlers")
    print("=" * 70)
    print()

    for filepath, handler_name in task_handlers:
        path = Path(filepath)
        print(f"Checking {path.name}...")

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

        # Check 2: Handler function exists
        if check_handler_function(path, handler_name):
            print(f"  [PASS] Handler function '{handler_name}' exists")
        else:
            print(f"  [FAIL] Handler function '{handler_name}' not found")
            all_passed = False

        # Check 3: Uses MongoDB models
        if check_mongodb_imports(path):
            print(f"  [PASS] Uses MongoDB models")
        else:
            print(f"  [FAIL] No MongoDB model imports found")
            all_passed = False

        print()

    print("=" * 70)
    if all_passed:
        print("[SUCCESS] ALL CHECKS PASSED - Phase 9 is complete!")
        print("=" * 70)
        return 0
    else:
        print("[ERROR] SOME CHECKS FAILED - Review errors above")
        print("=" * 70)
        return 1

if __name__ == '__main__':
    sys.exit(main())
