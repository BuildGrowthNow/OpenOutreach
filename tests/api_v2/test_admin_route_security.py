"""Regression checks for the admin router's explicit authorization boundary."""

import ast
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ADMIN_ROUTERS = [
    ROOT / "openoutreach" / "api_v2" / "routers" / "admin.py",
    ROOT / "openoutreach" / "api_v2" / "routers" / "admin_proxies.py",
]


def test_every_admin_route_declares_route_level_admin_dependency():
    missing = []
    route_count = 0
    for admin_router in ADMIN_ROUTERS:
        tree = ast.parse(admin_router.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                    continue
                if not isinstance(decorator.func.value, ast.Name) or decorator.func.value.id != "router":
                    continue
                if decorator.func.attr not in {"get", "post", "put", "patch", "delete"}:
                    continue
                route_count += 1
                has_dependency = any(
                    isinstance(keyword, ast.keyword)
                    and keyword.arg == "dependencies"
                    and "get_admin_user" in ast.unparse(keyword.value)
                    for keyword in decorator.keywords
                )
                if not has_dependency:
                    missing.append(f"{admin_router.name}:{node.name}")

    assert route_count
    assert not missing, f"admin routes missing explicit get_admin_user dependency: {missing}"


def test_linkedin_models_can_be_imported_before_mongodb_models():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from openoutreach.linkedin.models import LinkedInProfile; "
            "assert LinkedInProfile(is_active=True).is_active",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
