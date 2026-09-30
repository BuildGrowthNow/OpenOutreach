from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-scalingo.yml"


def test_scalingo_web_archive_has_explicit_node_buildpack():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    yaml.safe_load(workflow)

    assert '"${DEPLOY_SHA}:frontend"' in workflow
    assert "deploy /tmp/openoutreach-web.tgz" in workflow
    assert (ROOT / "frontend" / ".buildpacks").read_text(encoding="utf-8").strip() == (
        "https://github.com/Scalingo/nodejs-buildpack"
    )
