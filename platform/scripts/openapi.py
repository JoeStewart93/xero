from __future__ import annotations

import argparse
import difflib
import importlib
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import yaml

PLATFORM_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = PLATFORM_ROOT / "docs" / "api"
COMMON_ROOT = PLATFORM_ROOT / "common" / "python"


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    package_root: Path
    module: str
    openapi_path: Path


SERVICES = {
    "bff": ServiceSpec(
        name="bff",
        package_root=PLATFORM_ROOT / "services" / "bff-api",
        module="xero_bff.main",
        openapi_path=DOCS_ROOT / "bff.openapi.yaml",
    ),
    "c2": ServiceSpec(
        name="c2",
        package_root=PLATFORM_ROOT / "services" / "c2-api",
        module="xero_c2.main",
        openapi_path=DOCS_ROOT / "c2.openapi.yaml",
    ),
    "beacon-handler": ServiceSpec(
        name="beacon-handler",
        package_root=PLATFORM_ROOT / "services" / "beacon-handler",
        module="xero_beacon_handler.main",
        openapi_path=DOCS_ROOT / "beacon-handler.openapi.yaml",
    ),
    "scanner": ServiceSpec(
        name="scanner",
        package_root=PLATFORM_ROOT / "services" / "scanner",
        module="xero_scanner.main",
        openapi_path=DOCS_ROOT / "scanner.openapi.yaml",
    ),
}


def service_names(selection: str) -> Iterable[str]:
    if selection == "all":
        return SERVICES.keys()
    return (selection,)


def render_openapi(service: ServiceSpec) -> str:
    sys.path[:0] = [str(service.package_root), str(COMMON_ROOT)]
    module = importlib.import_module(service.module)
    schema = module.app.openapi()
    return yaml.safe_dump(schema, sort_keys=False, allow_unicode=True)


def export_openapi(selection: str) -> int:
    DOCS_ROOT.mkdir(parents=True, exist_ok=True)
    for name in service_names(selection):
        service = SERVICES[name]
        service.openapi_path.write_text(render_openapi(service), encoding="utf-8")
    return 0


def check_service_openapi(service: ServiceSpec) -> int:
    expected = render_openapi(service)
    if not service.openapi_path.exists():
        print(f"Missing OpenAPI spec: {service.openapi_path}", file=sys.stderr)
        return 1

    current = service.openapi_path.read_text(encoding="utf-8")
    if current == expected:
        return 0

    diff = difflib.unified_diff(
        current.splitlines(keepends=True),
        expected.splitlines(keepends=True),
        fromfile=str(service.openapi_path),
        tofile=f"generated-{service.name}.openapi.yaml",
    )
    sys.stderr.writelines(diff)
    return 1


def check_openapi(selection: str) -> int:
    returncode = 0
    for name in service_names(selection):
        returncode = max(returncode, check_service_openapi(SERVICES[name]))
    return returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Export or check Xero service OpenAPI specs.")
    parser.add_argument("command", choices=("export", "check"))
    parser.add_argument("service", choices=("all", *SERVICES.keys()), nargs="?", default="all")
    args = parser.parse_args()
    if args.command == "export":
        return export_openapi(args.service)
    return check_openapi(args.service)


if __name__ == "__main__":
    raise SystemExit(main())
