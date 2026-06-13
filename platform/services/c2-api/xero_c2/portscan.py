from __future__ import annotations

import asyncio
import ipaddress
import time
import uuid
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from xero_c2.scan_jobs import (
    SCAN_PROGRESS_BATCH_SIZE,
    ScanExecutionResult,
    create_scan_job,
    mark_abandoned_scan_jobs,
    persist_scan_progress,
    public_scan_chunk,
    public_scan_job,
    publish_scan_event,
    run_scan_job,
)

PORTSCAN_MODULE_ID = "builtin.portscan"
MAX_TARGET_ENTRIES = 10
MAX_EXPANDED_HOSTS = 256
MAX_TOTAL_PROBES = 65_535
IpAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
IpNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


class PortScanArgs(BaseModel):
    targets: list[str] = Field(min_length=1, max_length=MAX_TARGET_ENTRIES)
    port_range: str = Field(min_length=1, max_length=512)
    timeout_ms: int = Field(default=1000, ge=50, le=60_000)
    max_threads: int = Field(default=64, ge=1, le=256)
    execution_target: str = "auto"

    @field_validator("execution_target")
    @classmethod
    def validate_execution_target(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized != "auto":
            raise ValueError("F0022 supports execution_target=auto only")
        return normalized

    @field_validator("targets")
    @classmethod
    def normalize_targets(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value if item.strip()]
        if not normalized:
            raise ValueError("At least one target is required")
        if len(normalized) > MAX_TARGET_ENTRIES:
            raise ValueError(f"At most {MAX_TARGET_ENTRIES} target entries are allowed")
        return normalized

    @field_validator("port_range")
    @classmethod
    def normalize_port_range(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("port_range cannot be blank")
        parse_ports(normalized)
        return normalized

    @model_validator(mode="after")
    def validate_probe_budget(self) -> PortScanArgs:
        total = estimate_portscan_progress_total(self.model_dump())
        if total > MAX_TOTAL_PROBES:
            raise ValueError(f"Scan probe budget exceeds {MAX_TOTAL_PROBES}")
        return self


@dataclass(frozen=True)
class Probe:
    host: str
    port: int


def parse_ports(value: str) -> list[int]:
    ports: set[int] = set()
    for raw_part in value.split(","):
        part = raw_part.strip()
        if not part:
            continue
        if "-" in part:
            raw_start, raw_end = part.split("-", 1)
            try:
                start = int(raw_start.strip())
                end = int(raw_end.strip())
            except ValueError as exc:
                raise ValueError("port_range contains an invalid range") from exc
            if end < start:
                raise ValueError("port_range cannot contain descending ranges")
            for port in range(start, end + 1):
                _validate_port(port)
                ports.add(port)
        else:
            try:
                port = int(part)
            except ValueError as exc:
                raise ValueError("port_range contains an invalid port") from exc
            _validate_port(port)
            ports.add(port)
    if not ports:
        raise ValueError("port_range must include at least one port")
    return sorted(ports)


def validate_port_number(port: int) -> int:
    _validate_port(port)
    return port


def _validate_port(port: int) -> None:
    if port < 1 or port > 65_535:
        raise ValueError("Ports must be between 1 and 65535")


def expand_targets(targets: list[str]) -> list[str]:
    expanded: list[str] = []
    for target in targets:
        expanded.extend(_expand_target(target))
        if len(expanded) > MAX_EXPANDED_HOSTS:
            raise ValueError(f"Target expansion exceeds {MAX_EXPANDED_HOSTS} hosts")
    seen: set[str] = set()
    unique: list[str] = []
    for host in expanded:
        if host not in seen:
            seen.add(host)
            unique.append(host)
    return unique


def normalize_single_host(host: str) -> str:
    expanded = expand_targets([host])
    if len(expanded) != 1:
        raise ValueError("Service enumeration host must resolve to exactly one lab host")
    return expanded[0]


def _expand_target(target: str) -> list[str]:
    normalized = target.strip().lower()
    if normalized == "localhost":
        return ["127.0.0.1"]
    try:
        network = ipaddress.ip_network(normalized, strict=False)
    except ValueError:
        try:
            address = ipaddress.ip_address(normalized)
        except ValueError as exc:
            raise ValueError("Targets must be loopback/private/link-local IPs, CIDRs, or localhost") from exc
        _validate_scoped_address(address)
        return [str(address)]
    _validate_scoped_network(network)
    if network.prefixlen == network.max_prefixlen:
        return [str(network.network_address)]
    return [str(address) for address in network.hosts()]


def _validate_scoped_network(network: IpNetwork) -> None:
    for address in (network.network_address, network.broadcast_address):
        _validate_scoped_address(address)


def _validate_scoped_address(address: IpAddress) -> None:
    if address.is_loopback or address.is_private or address.is_link_local:
        return
    raise ValueError("Public targets are rejected until backend project scope enforcement exists")


def normalized_portscan_args(raw_args: dict[str, Any]) -> dict[str, Any]:
    args = PortScanArgs.model_validate(raw_args)
    return args.model_dump()


def estimate_portscan_progress_total(args: dict[str, Any]) -> int:
    return len(expand_targets(args["targets"])) * len(parse_ports(args["port_range"]))


def portscan_initial_state_counts() -> dict[str, int]:
    return {"closed": 0, "filtered": 0, "open": 0}


async def run_portscan_scan_job(
    app: Any,
    settings,
    scan_job_id: uuid.UUID,
    raw_args: dict[str, Any],
    started_at: float,
) -> ScanExecutionResult:
    args = PortScanArgs.model_validate(raw_args)
    hosts = expand_targets(args.targets)
    ports = parse_ports(args.port_range)
    probes = [Probe(host, port) for host in hosts for port in ports]
    state_counts = portscan_initial_state_counts()
    all_results: list[dict[str, Any]] = []
    pending_results: list[dict[str, Any]] = []
    completed = 0
    sequence = 0
    semaphore = asyncio.Semaphore(args.max_threads)

    async def bounded_probe(probe: Probe) -> dict[str, Any]:
        async with semaphore:
            return await probe_tcp_connect(probe.host, probe.port, timeout_ms=args.timeout_ms)

    for future in asyncio.as_completed([bounded_probe(probe) for probe in probes]):
        result = await future
        completed += 1
        state_counts[result["state"]] += 1
        all_results.append(result)
        pending_results.append(result)
        if len(pending_results) >= SCAN_PROGRESS_BATCH_SIZE:
            sequence += 1
            await persist_scan_progress(
                app,
                settings,
                scan_job_id,
                sequence=sequence,
                kind="progress",
                results=pending_results,
                completed=completed,
                total=len(probes),
                state_counts=state_counts,
            )
            pending_results = []

    if pending_results:
        sequence += 1
        await persist_scan_progress(
            app,
            settings,
            scan_job_id,
            sequence=sequence,
            kind="progress",
            results=pending_results,
            completed=completed,
            total=len(probes),
            state_counts=state_counts,
        )

    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
    summary = {
        "duration_ms": duration_ms,
        "hosts_scanned": len(hosts),
        "open_count": state_counts["open"],
        "ports_scanned": len(probes),
        "state_counts": state_counts,
    }
    all_results.sort(key=lambda item: (item["host"], item["port"]))
    return ScanExecutionResult(
        results=all_results,
        summary=summary,
        state_counts=state_counts,
        probes_completed=len(probes),
        probes_total=len(probes),
        next_sequence=sequence + 1,
    )


async def probe_tcp_connect(host: str, port: int, *, timeout_ms: int) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout_ms / 1000)
        writer.close()
        with suppress(Exception):
            await writer.wait_closed()
        state = "open"
    except TimeoutError:
        state = "filtered"
    except (ConnectionRefusedError, ConnectionResetError):
        state = "closed"
    except OSError as exc:
        state = "closed" if _is_refused_error(exc) else "filtered"
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    return {"host": host, "latency_ms": latency_ms, "port": port, "state": state}


def _is_refused_error(exc: OSError) -> bool:
    refused_codes = {10061, 111, 61}
    errno = getattr(exc, "errno", None)
    winerror = getattr(exc, "winerror", None)
    return errno in refused_codes or winerror in refused_codes
