from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

import yaml

PLATFORM_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PLATFORM_ROOT / "backend"
OPENAPI_PATH = PLATFORM_ROOT / "docs" / "api" / "openapi.yaml"

sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app  # noqa: E402


def render_openapi() -> str:
    schema = app.openapi()
    return yaml.safe_dump(schema, sort_keys=False, allow_unicode=True)


def export_openapi() -> int:
    OPENAPI_PATH.parent.mkdir(parents=True, exist_ok=True)
    OPENAPI_PATH.write_text(render_openapi(), encoding="utf-8")
    return 0


def check_openapi() -> int:
    expected = render_openapi()
    if not OPENAPI_PATH.exists():
        print(f"Missing OpenAPI spec: {OPENAPI_PATH}", file=sys.stderr)
        return 1

    current = OPENAPI_PATH.read_text(encoding="utf-8")
    if current == expected:
        return 0

    diff = difflib.unified_diff(
        current.splitlines(keepends=True),
        expected.splitlines(keepends=True),
        fromfile=str(OPENAPI_PATH),
        tofile="generated-openapi.yaml",
    )
    sys.stderr.writelines(diff)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Export or check the Xero Core OpenAPI spec.")
    parser.add_argument("command", choices=("export", "check"))
    args = parser.parse_args()
    if args.command == "export":
        return export_openapi()
    return check_openapi()


if __name__ == "__main__":
    raise SystemExit(main())
