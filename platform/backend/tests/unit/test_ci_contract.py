import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
PLATFORM_ROOT = REPO_ROOT / "platform"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"
CI_SCRIPT = PLATFORM_ROOT / "scripts" / "ci.py"
OPENAPI_PATH = PLATFORM_ROOT / "docs" / "api" / "openapi.yaml"


def load_workflow() -> dict:
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def test_workflow_yaml_defines_required_triggers_and_permissions():
    workflow = load_workflow()

    assert workflow["on"]["push"]["branches"] == ["main"]
    assert workflow["on"]["pull_request"]["branches"] == ["main"]
    assert "workflow_dispatch" in workflow["on"]
    assert workflow["permissions"] == {"contents": "read"}


def test_workflow_defines_required_jobs_and_artifacts():
    workflow = load_workflow()
    jobs = workflow["jobs"]

    assert set(jobs) == {"backend", "frontend", "docker-build", "compose-e2e"}
    assert jobs["backend"]["name"] == "backend"
    assert jobs["frontend"]["name"] == "frontend"
    assert jobs["docker-build"]["name"] == "docker-build"
    assert jobs["compose-e2e"]["name"] == "compose-e2e"

    workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "docker/build-push-action@v7" in workflow_text
    assert "actions/upload-artifact@v7" in workflow_text
    assert "npx --prefix frontend playwright install --with-deps chromium" in workflow_text


def test_ci_script_exits_nonzero_when_child_command_fails():
    completed = subprocess.run(
        [sys.executable, str(CI_SCRIPT), "fail-probe"],
        cwd=PLATFORM_ROOT,
        check=False,
    )

    assert completed.returncode != 0


def test_openapi_spec_is_tracked():
    assert OPENAPI_PATH.exists()
    assert "openapi: 3.1.0" in OPENAPI_PATH.read_text(encoding="utf-8")
