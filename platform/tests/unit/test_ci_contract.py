from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
PLATFORM_ROOT = REPO_ROOT / "platform"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"
CI_SCRIPT = PLATFORM_ROOT / "scripts" / "ci.py"
OPENAPI_ROOT = PLATFORM_ROOT / "docs" / "api"


def load_workflow() -> dict:
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def test_workflow_yaml_defines_required_jobs():
    workflow = load_workflow()

    assert workflow["on"]["push"]["branches"] == ["main"]
    assert workflow["on"]["pull_request"]["branches"] == ["main"]
    assert set(workflow["jobs"]) == {"backend", "frontend", "docker-build", "compose-e2e"}


def test_ci_script_exits_nonzero_when_child_command_fails():
    completed = subprocess.run(
        [sys.executable, str(CI_SCRIPT), "fail-probe"],
        cwd=PLATFORM_ROOT,
        check=False,
    )

    assert completed.returncode != 0


def test_service_openapi_specs_are_tracked():
    for filename in (
        "bff.openapi.yaml",
        "c2.openapi.yaml",
        "beacon-handler.openapi.yaml",
        "scanner.openapi.yaml",
    ):
        path = OPENAPI_ROOT / filename
        assert path.exists()
        assert "openapi: 3.1.0" in path.read_text(encoding="utf-8")
