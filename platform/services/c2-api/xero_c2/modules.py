from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ModuleDefinition(BaseModel):
    id: str
    name: str
    category: str
    description: str
    source: str = "builtin"
    author: str = "Xero"
    version: str = "0.1.0"
    status: str = "enabled"
    disabled_reason: str | None = None
    plugin_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    updated_at: str | None = None
    documentation_url: str | None = None
    execution_kind: str
    supported_execution_targets: list[str] = Field(default_factory=list)
    required_capabilities: list[str] = Field(default_factory=list)
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

SERVICEENUM_ARGS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["host", "ports"],
    "properties": {
        "host": {
            "type": "string",
            "description": "One loopback, private, or link-local lab host.",
        },
        "ports": {
            "type": "array",
            "items": {"type": "integer", "minimum": 1, "maximum": 65535},
            "maxItems": 100,
            "description": "Open TCP ports to enumerate, usually derived from a port scan result.",
        },
        "probe_timeout_ms": {"type": "integer", "minimum": 50, "maximum": 60000, "default": 1000},
        "max_threads": {"type": "integer", "minimum": 1, "maximum": 64, "default": 16},
        "execution_target": {"type": "string", "enum": ["auto"], "default": "auto"},
        "source_scan_job_id": {"type": "string", "format": "uuid"},
    },
}

SERVICEENUM_RESULT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["host", "port", "transport", "status", "service_guess", "confidence", "latency_ms"],
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                    "transport": {"type": "string", "enum": ["tcp"]},
                    "status": {"type": "string", "enum": ["error", "identified", "skipped", "timeout", "unknown"]},
                    "service_guess": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "banner": {"type": "string"},
                    "tls": {"type": ["object", "null"]},
                    "evidence": {"type": "array", "items": {"type": "object"}},
                    "latency_ms": {"type": "number"},
                    "error": {"type": ["string", "null"]},
                },
            },
        },
        "summary": {
            "type": "object",
            "properties": {
                "duration_ms": {"type": "number"},
                "host": {"type": "string"},
                "identified_count": {"type": "integer"},
                "ports_enumerated": {"type": "integer"},
                "source_scan_job_id": {"type": ["string", "null"]},
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
        required_capabilities=[],
        tags=["command", "beacon-task", "utility"],
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
        required_capabilities=["tcp-connect"],
        tags=["recon", "tcp", "scan-job"],
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
    ModuleDefinition(
        id="builtin.serviceenum",
        name="Service Enumeration",
        category="scanning",
        description=(
            "Probe open TCP ports for banners, HTTP headers, TLS certificate metadata, and service fingerprints."
        ),
        execution_kind="scan-job",
        supported_execution_targets=["auto"],
        required_capabilities=["service-enumeration"],
        tags=["recon", "service-enumeration", "scan-job"],
        args_schema=SERVICEENUM_ARGS_SCHEMA,
        result_schema=SERVICEENUM_RESULT_SCHEMA,
        example={
            "module": "builtin.serviceenum",
            "args": {
                "execution_target": "auto",
                "host": "127.0.0.1",
                "ports": [22, 80, 443],
                "probe_timeout_ms": 1000,
                "source_scan_job_id": None,
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
