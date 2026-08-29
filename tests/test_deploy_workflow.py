from pathlib import Path

import yaml


WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "deploy-aws.yml"


def test_production_deploy_is_manual_and_confirmed():
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    triggers = workflow.get("on", workflow.get(True))
    assert "push" not in triggers
    dispatch = triggers["workflow_dispatch"]
    confirmation = dispatch["inputs"]["confirm_production_deploy"]
    assert confirmation["required"] is True
    assert confirmation["type"] == "boolean"
    assert workflow["jobs"]["deploy"]["environment"]["name"] == "production"
    assert "confirm_production_deploy == true" in workflow["jobs"]["deploy"]["if"]


def test_deploy_pins_remote_checkout_and_build_identity():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "git checkout --detach '${DEPLOY_SHA}'" in workflow
    assert "BUILD_COMMIT='${DEPLOY_SHA}'" in workflow
    assert "APP_VERSION='${APP_VERSION}'" in workflow
    assert "id: version" in workflow
    assert "openoutreach/desktop/__version__.py" in workflow
    assert "node.value.value" in workflow
    assert 'APP_VERSION: ${{ steps.version.outputs.app_version }}' in workflow
    assert 'APP_VERSION: "2.1.2"' not in workflow


def test_deploy_fails_when_health_timeout_expires():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "ERROR: Container did not reach healthy state in time" in workflow
    assert "docker compose ps -a" in workflow
    assert "echo 'ERROR: Container did not reach healthy state in time'\n            docker compose ps -a\n            exit 1" in workflow


def test_deploy_uses_pinned_ssh_host_keys():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "EC2_KNOWN_HOSTS: ${{ secrets.EC2_KNOWN_HOSTS }}" in workflow
    assert "ssh-keyscan" not in workflow
    assert "StrictHostKeyChecking=yes" in workflow
    assert "StrictHostKeyChecking=no" not in workflow


def test_deploy_verifies_live_build_identity_and_cache_policy():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "name: Verify deployed build identity" in workflow
    assert "Cache-Control: no-store" in workflow
    assert ".build.version" in workflow
    assert ".build.commit" in workflow
    assert "EXPECTED_COMMIT: ${{ env.DEPLOY_SHA }}" in workflow


def test_deploy_health_probe_uses_canonical_api_hostname():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "https://outreach-api.lengrowth.com/api/health" in workflow
    assert "https://outreach.lengrowth.com/api/health" not in workflow
