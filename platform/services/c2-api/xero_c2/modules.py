from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ModuleDefinition(BaseModel):
    id: str
    name: str
    category: str
    description: str
    source: str = "builtin"
    version: str = "0.1.0"
    execution_kind: str
    supported_execution_targets: list[str] = Field(default_factory=list)
    args_schema: dict[str, Any]
    result_schema: dict[str, Any]
    example: dict[str, Any]


PORTSCAN_ARGS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["targets", "port_range"],
    "properties": {
        "targets": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 10,
            "description": "Loopback, private, or link-local lab targets. CIDR entries are expanded server-side.",
        },
        "port_range": {
            "type": "string",
            "description": "Comma separated ports and ranges, such as 22,80,443,8000-8010.",
        },
        "timeout_ms": {"type": "integer", "minimum": 50, "maximum": 60000, "default": 1000},
        "max_threads": {"type": "integer", "minimum": 1, "maximum": 256, "default": 64},
        "execution_target": {"type": "string", "enum": ["auto"], "default": "auto"},
    },
}

PORTSCAN_RESULT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["host", "port", "state", "latency_ms"],
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                    "state": {"type": "string", "enum": ["closed", "filtered", "open"]},
                    "latency_ms": {"type": "number"},
                },
            },
        },
        "summary": {
            "type": "object",
            "properties": {
                "duration_ms": {"type": "number"},
                "hosts_scanned": {"type": "integer"},
                "open_count": {"type": "integer"},
                "ports_scanned": {"type": "integer"},
                "state_counts": {"type": "object"},
            },
        },
    },
}


BUILTIN_MODULES: list[ModuleDefinition] = [
    ModuleDefinition(
        id="shell",
        name="Shell Command",
        category="utility",
        description="Queue a shell command for an active beacon.",
        execution_kind="beacon-task",
        supported_execution_targets=["beacon"],
        args_schema={
            "type": "object",
            "required": ["command"],
            "properties": {
                "command": {"type": "string", "minLength": 1},
                "shell_type": {"type": "string", "enum": ["auto", "bash", "cmd", "powershell"], "default": "auto"},
                "timeout_seconds": {"type": "integer", "minimum": 1},
            },
        },
        result_schema={"type": "object", "properties": {"stdout": {"type": "string"}, "stderr": {"type": "string"}}},
        example={"module": "shell", "args": {"command": "whoami", "shell_type": "auto"}},
    ),
    ModuleDefinition(
        id="builtin.portscan",
        name="Port Scan",
        category="scanning",
        description="Run an embedded C2 TCP connect scan against authorized lab targets.",
        execution_kind="scan-job",
        supported_execution_targets=["auto"],
        args_schema=PORTSCAN_ARGS_SCHEMA,
        result_schema=PORTSCAN_RESULT_SCHEMA,
        example={
            "module": "builtin.portscan",
            "args": {
                "execution_target": "auto",
                "max_threads": 32,
                "port_range": "22,80,443",
                "targets": ["127.0.0.1"],
                "timeout_ms": 1000,
            },
        },
    ),
]


def list_modules() -> list[dict[str, Any]]:
    return [module.model_dump() for module in BUILTIN_MODULES]


def module_definition(module_id: str) -> dict[str, Any] | None:
    for module in BUILTIN_MODULES:
        if module.id == module_id:
            return module.model_dump()
    return None
