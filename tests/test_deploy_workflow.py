from pathlib import Path

import yaml


WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "deploy-scalingo.yml"


def test_production_deploy_is_manual_and_protected_by_ci():
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    triggers = workflow.get("on", workflow.get(True))
    assert "push" not in triggers
    assert "workflow_dispatch" in triggers
    assert workflow["jobs"]["production"]["needs"] == "test"
    assert workflow["jobs"]["production"]["environment"] == "production"


def test_deploy_targets_scalingo_apps_in_production_region():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "SCALINGO_REGION: osc-fr1" in workflow
    assert "--app outreach-api --region \"$SCALINGO_REGION\" deploy" in workflow
    assert "--app outreach-web --region \"$SCALINGO_REGION\" deploy" in workflow
    assert "SCALINGO_API_TOKEN: ${{ secrets.SCALINGO_API_TOKEN }}" in workflow
    assert "git archive --format=tar \"$DEPLOY_SHA\" -- . ':(exclude)frontend' ':(exclude)package.json' ':(exclude)package-lock.json' | gzip -c > /tmp/openoutreach-api.tgz" in workflow


def test_deploy_validates_public_health_and_web_root():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "https://outreach-api.lengrowth.com/api/health" in workflow
    assert "https://outreach.lengrowth.com/" in workflow
    assert "HOSTNAME=0.0.0.0 node .next/standalone/server.js" in (WORKFLOW.parents[2] / "frontend" / "Procfile").read_text(encoding="utf-8")


def test_deploy_does_not_reference_retired_aws_infrastructure():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "EC2" not in workflow
    assert "AWS" not in workflow
