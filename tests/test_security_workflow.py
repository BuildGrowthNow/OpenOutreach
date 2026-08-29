from pathlib import Path

import yaml


WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "security-scan.yml"


def test_security_workflow_uses_read_only_repository_permissions():
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert workflow["permissions"] == {"contents": "read"}


def test_security_workflow_publishes_python_sbom():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "python scripts/generate_sbom.py --output SBOM.cyclonedx.json" in workflow
    assert "name: python-sbom" in workflow


def test_security_workflow_runs_logger_redaction_regression():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "tests/test_logging_redaction.py" in workflow
    assert "tests/test_desktop_log_audit.py" in workflow


def test_security_workflow_builds_frontend_from_locked_dependencies():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "frontend-regression:" in workflow
    assert "cache-dependency-path: frontend/package-lock.json" in workflow
    assert "working-directory: frontend" in workflow
    assert "npm ci" in workflow
    assert "npm audit --omit=dev --audit-level=high" in workflow
    assert "npm run lint" in workflow
    assert "npm run build" in workflow
