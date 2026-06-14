from __future__ import annotations

import asyncio
import ipaddress
import shutil
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET
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
SAFE_NMAP_SCRIPT_CATEGORIES = {
    "auth",
    "broadcast",
    "default",
    "discovery",
    "external",
    "safe",
    "version",
    "vuln",
}
DISRUPTIVE_NMAP_SCRIPT_CATEGORIES = {"dos", "exploit", "intrusive", "malware"}
NMAP_SCRIPT_CATEGORIES = SAFE_NMAP_SCRIPT_CATEGORIES | DISRUPTIVE_NMAP_SCRIPT_CATEGORIES


class PortScanArgs(BaseModel):
    allow_disruptive_scripts: bool = False
    targets: list[str] = Field(min_length=1, max_length=MAX_TARGET_ENTRIES)
    port_range: str = Field(min_length=1, max_length=512)
    timeout_ms: int = Field(default=1000, ge=50, le=60_000)
    max_threads: int = Field(default=64, ge=1, le=256)
    scan_engine: str = "nmap"
    scan_technique: str = "tcp-connect"
    script_categories: list[str] = Field(default_factory=list, max_length=8)
    script_scan_enabled: bool = False
    timing_template: int = Field(default=3, ge=0, le=5)
    service_detection: bool = False
    os_detection: bool = False
    dns_resolution: bool = False
    execution_target: str = "auto"

    @field_validator("scan_engine")
    @classmethod
    def validate_scan_engine(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized != "nmap":
            raise ValueError("Port scans use scan_engine=nmap")
        return normalized

    @field_validator("scan_technique")
    @classmethod
    def validate_scan_technique(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"tcp-connect", "syn", "udp"}:
            raise ValueError("scan_technique must be tcp-connect, syn, or udp")
        return normalized

    @field_validator("execution_target")
    @classmethod
    def validate_execution_target(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized in {"auto", "distributed"}:
            return normalized
        if normalized.startswith("scanner:"):
            try:
                uuid.UUID(normalized.removeprefix("scanner:"))
            except ValueError as exc:
                raise ValueError("execution_target scanner selector must be scanner:<worker-id>") from exc
            return normalized
        raise ValueError("execution_target must be auto, distributed, or scanner:<worker-id>")

    @field_validator("script_categories")
    @classmethod
    def validate_script_categories(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for category in value:
            item = category.strip().lower()
            if not item:
                continue
            if item not in NMAP_SCRIPT_CATEGORIES:
                raise ValueError("script_categories contains an unsupported NMAP category")
            if item not in normalized:
                normalized.append(item)
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
        if not self.script_scan_enabled:
            self.script_categories = []
        elif not self.script_categories:
            self.script_categories = ["default", "safe"]
        if not self.allow_disruptive_scripts:
            requested_disruptive = set(self.script_categories) & DISRUPTIVE_NMAP_SCRIPT_CATEGORIES
            if requested_disruptive:
                requested = ", ".join(sorted(requested_disruptive))
                raise ValueError(f"Disruptive NMAP script categories require allow_disruptive_scripts=true: {requested}")
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
    if should_use_nmap():
        return await run_nmap_portscan_scan_job(app, settings, scan_job_id, args, hosts, ports, started_at)
    return await run_tcp_connect_portscan_scan_job(app, settings, scan_job_id, args, hosts, ports, started_at)


def should_use_nmap() -> bool:
    return shutil.which("nmap") is not None and getattr(probe_tcp_connect, "__name__", "") == "probe_tcp_connect"


async def run_tcp_connect_portscan_scan_job(
    app: Any,
    settings,
    scan_job_id: uuid.UUID,
    args: PortScanArgs,
    hosts: list[str],
    ports: list[int],
    started_at: float,
) -> ScanExecutionResult:
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


async def run_nmap_portscan_scan_job(
    app: Any,
    settings,
    scan_job_id: uuid.UUID,
    args: PortScanArgs,
    hosts: list[str],
    ports: list[int],
    started_at: float,
) -> ScanExecutionResult:
    executable = shutil.which("nmap")
    if executable is None:
        raise RuntimeError("NMAP executable is not available")

    cmd = build_nmap_command(executable, args, hosts, ports)
    timeout_seconds = max(30, min(900, int((len(hosts) * len(ports) * args.timeout_ms / 1000) + 30)))
    completed = subprocess.run(
        cmd,
        capture_output=True,
        check=False,
        text=True,
        timeout=timeout_seconds,
    )
    if completed.returncode not in {0, 1} and not completed.stdout.strip():
        stderr = completed.stderr.strip() or f"NMAP exited with code {completed.returncode}"
        raise RuntimeError(stderr[:512])

    all_results = parse_nmap_xml(completed.stdout, hosts, ports)
    state_counts = portscan_initial_state_counts()
    sequence = 0
    completed_count = 0
    pending_results: list[dict[str, Any]] = []
    for result in all_results:
        completed_count += 1
        state_counts[result["state"]] += 1
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
                completed=completed_count,
                total=len(all_results),
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
            completed=completed_count,
            total=len(all_results),
            state_counts=state_counts,
        )

    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
    summary = {
        "duration_ms": duration_ms,
        "hosts_scanned": len(hosts),
        "open_count": state_counts["open"],
        "ports_scanned": len(all_results),
        "scanner": "nmap",
        "state_counts": state_counts,
    }
    return ScanExecutionResult(
        results=all_results,
        summary=summary,
        state_counts=state_counts,
        probes_completed=len(all_results),
        probes_total=len(all_results),
        next_sequence=sequence + 1,
    )


def build_nmap_command(executable: str, args: PortScanArgs, hosts: list[str], ports: list[int]) -> list[str]:
    cmd = [
        executable,
        "-oX",
        "-",
        "-p",
        ",".join(str(port) for port in ports),
        f"-T{args.timing_template}",
        "--host-timeout",
        f"{max(10, int((len(ports) * args.timeout_ms / 1000) + 10))}s",
        "-Pn",
    ]
    if not args.dns_resolution:
        cmd.append("-n")
    if args.scan_technique == "syn":
        cmd.append("-sS")
    elif args.scan_technique == "udp":
        cmd.append("-sU")
    else:
        cmd.append("-sT")
    if args.service_detection:
        cmd.append("-sV")
    if args.os_detection:
        cmd.append("-O")
    if args.script_scan_enabled:
        cmd.extend(["--script", ",".join(args.script_categories or ["default", "safe"])])
    cmd.extend(hosts)
    return cmd


def parse_nmap_xml(xml_output: str, hosts: list[str], ports: list[int]) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(xml_output)
    except ET.ParseError as exc:
        raise RuntimeError("Unable to parse NMAP XML output") from exc

    results_by_endpoint: dict[tuple[str, int], dict[str, Any]] = {}
    known_hosts = set(hosts)
    for host_node in root.findall("host"):
        address_node = host_node.find("address")
        host = address_node.get("addr") if address_node is not None else ""
        if host not in known_hosts:
            hostnames = [
                item.get("name", "")
                for item in host_node.findall("./hostnames/hostname")
                if item.get("name")
            ]
            host = next((candidate for candidate in hostnames if candidate in known_hosts), host)
        if not host:
            continue
        latency_ms = _nmap_host_latency_ms(host_node)
        for port_node in host_node.findall("./ports/port"):
            try:
                port = int(port_node.get("portid", "0"))
            except ValueError:
                continue
            if port not in ports:
                continue
            state_node = port_node.find("state")
            state = normalize_nmap_state(state_node.get("state") if state_node is not None else None)
            results_by_endpoint[(host, port)] = {
                "host": host,
                "latency_ms": latency_ms,
                "port": port,
                "state": state,
            }

    results = [
        results_by_endpoint.get(
            (host, port),
            {"host": host, "latency_ms": 0.0, "port": port, "state": "filtered"},
        )
        for host in hosts
        for port in ports
    ]
    return sorted(results, key=lambda item: (item["host"], item["port"]))


def normalize_nmap_state(state: str | None) -> str:
    if state in {"open", "closed", "filtered"}:
        return state
    if state in {"open|filtered", "unfiltered"}:
        return "filtered"
    return "closed"


def _nmap_host_latency_ms(host_node: ET.Element) -> float:
    times_node = host_node.find("times")
    if times_node is None:
        return 0.0
    srtt = times_node.get("srtt")
    if not srtt:
        return 0.0
    with suppress(ValueError):
        return round(int(srtt) / 1000, 2)
    return 0.0


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
