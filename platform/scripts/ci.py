from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

PLATFORM_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PLATFORM_ROOT.parent


def with_pythonpath(env: dict[str, str] | None = None) -> dict[str, str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    paths = [
        str(PLATFORM_ROOT / "common" / "python"),
        str(PLATFORM_ROOT / "services" / "bff-api"),
        str(PLATFORM_ROOT / "services" / "c2-api"),
        str(PLATFORM_ROOT / "services" / "beacon-handler"),
        str(PLATFORM_ROOT / "services" / "scanner"),
    ]
    existing = merged.get("PYTHONPATH")
    joined = os.pathsep.join(paths)
    merged["PYTHONPATH"] = joined if not existing else f"{joined}{os.pathsep}{existing}"
    return merged


def run(args: Sequence[str], *, cwd: Path = PLATFORM_ROOT, env: dict[str, str] | None = None) -> int:
    completed = subprocess.run(list(args), cwd=cwd, env=env, check=False)
    return completed.returncode


def node_bin(name: str) -> str:
    return f"{name}.cmd" if os.name == "nt" else name


def run_many(commands: Sequence[Sequence[str]], *, env: dict[str, str] | None = None) -> int:
    for command in commands:
        returncode = run(command, env=env)
        if returncode != 0:
            return returncode
    return 0


def command_backend_lint() -> int:
    return run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "common/python",
            "services",
            "tests",
            "features",
            "scripts",
        ],
        env=with_pythonpath(),
    )


def command_backend_unit() -> int:
    return run([sys.executable, "-m", "pytest", "tests/unit"], env=with_pythonpath())


def command_backend_integration() -> int:
    return run([sys.executable, "-m", "pytest", "tests/integration"], env=with_pythonpath())


def command_backend_behave() -> int:
    return run([sys.executable, "-m", "behave", "features"], env=with_pythonpath())


def command_openapi_export() -> int:
    return run([sys.executable, "scripts/openapi.py", "export"], env=with_pythonpath())


def command_openapi_check() -> int:
    return run([sys.executable, "scripts/openapi.py", "check"], env=with_pythonpath())


def command_frontend_lint() -> int:
    return run([node_bin("npm"), "--prefix", "frontend", "run", "lint"])


def command_frontend_test() -> int:
    return run([node_bin("npm"), "--prefix", "frontend", "test", "--", "--run"])


def command_frontend_build() -> int:
    return run([node_bin("npm"), "--prefix", "frontend", "run", "build"])


def command_playwright() -> int:
    return run([node_bin("npm"), "--prefix", "frontend", "run", "test:e2e"])


def command_go_protocol_test() -> int:
    protocol_root = PLATFORM_ROOT / "protocol" / "go"
    if shutil.which("go"):
        return run(["go", "test", "./..."], cwd=protocol_root)
    docker = shutil.which("docker")
    if not docker:
        print("Go toolchain and Docker fallback are unavailable.", file=sys.stderr)
        return 1
    return run(
        [
            docker,
            "run",
            "--rm",
            "-v",
            f"{PLATFORM_ROOT / 'protocol'}:/workspace/protocol",
            "-w",
            "/workspace/protocol/go",
            "golang:1.26",
            "go",
            "test",
            "./...",
        ]
    )


def command_go_beacon_test() -> int:
    beacon_root = PLATFORM_ROOT / "beacons" / "go"
    if shutil.which("go"):
        return run(["go", "test", "./..."], cwd=beacon_root)
    docker = shutil.which("docker")
    if not docker:
        print("Go toolchain and Docker fallback are unavailable.", file=sys.stderr)
        return 1
    return run(
        [
            docker,
            "run",
            "--rm",
            "-v",
            f"{PLATFORM_ROOT}:/workspace/platform",
            "-w",
            "/workspace/platform/beacons/go",
            "golang:1.26",
            "go",
            "test",
            "./...",
        ]
    )


def command_go_beacon_build() -> int:
    beacon_root = PLATFORM_ROOT / "beacons" / "go"
    build_script = (
        "go test ./... && "
        "CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -o /tmp/xero-beacon-linux-amd64 . && "
        "CGO_ENABLED=0 GOOS=windows GOARCH=amd64 go build -trimpath -o /tmp/xero-beacon-windows-amd64.exe ."
    )
    if shutil.which("go"):
        return run(["sh", "-c", build_script], cwd=beacon_root) if os.name != "nt" else run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "go test ./...; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; "
                "$env:CGO_ENABLED='0'; $env:GOOS='linux'; $env:GOARCH='amd64'; "
                "go build -trimpath -o $env:TEMP\\xero-beacon-linux-amd64 .; "
                "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; "
                "$env:GOOS='windows'; $env:GOARCH='amd64'; "
                "go build -trimpath -o $env:TEMP\\xero-beacon-windows-amd64.exe .",
            ],
            cwd=beacon_root,
        )
    docker = shutil.which("docker")
    if not docker:
        print("Go toolchain and Docker fallback are unavailable.", file=sys.stderr)
        return 1
    return run(
        [
            docker,
            "run",
            "--rm",
            "-v",
            f"{PLATFORM_ROOT}:/workspace/platform",
            "-w",
            "/workspace/platform/beacons/go",
            "golang:1.26",
            "sh",
            "-c",
            build_script,
        ]
    )


def command_fail_probe() -> int:
    return 1


COMMANDS = {
    "backend-lint": command_backend_lint,
    "backend-unit": command_backend_unit,
    "backend-integration": command_backend_integration,
    "backend-behave": command_backend_behave,
    "openapi-export": command_openapi_export,
    "openapi-check": command_openapi_check,
    "frontend-lint": command_frontend_lint,
    "frontend-test": command_frontend_test,
    "go-beacon-build": command_go_beacon_build,
    "go-beacon-test": command_go_beacon_test,
    "go-protocol-test": command_go_protocol_test,
    "frontend-build": command_frontend_build,
    "playwright": command_playwright,
    "fail-probe": command_fail_probe,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Xero CI command groups.")
    parser.add_argument("command", choices=sorted(COMMANDS))
    args = parser.parse_args()
    return COMMANDS[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())
