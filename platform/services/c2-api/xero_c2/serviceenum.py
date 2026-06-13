from __future__ import annotations

import asyncio
import re
import ssl
import time
import uuid
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC
from typing import Any

from cryptography import x509
from cryptography.x509.oid import ExtensionOID, NameOID
from pydantic import BaseModel, Field, field_validator

from xero_c2.portscan import normalize_single_host, validate_port_number
from xero_c2.scan_jobs import SCAN_PROGRESS_BATCH_SIZE, ScanExecutionResult, persist_scan_progress

SERVICEENUM_MODULE_ID = "builtin.serviceenum"
MAX_SERVICE_ENUM_PORTS = 100
DEFAULT_SERVICEENUM_THREADS = 16
TLS_PORT_HINTS = {443, 465, 563, 636, 853, 989, 990, 993, 995, 3389, 5986, 8443, 9443}
HTTP_PORT_HINTS = {80, 443, 8000, 8001, 8008, 8080, 8081, 8443, 8888, 9000, 9443}


class ServiceEnumArgs(BaseModel):
    host: str = Field(min_length=1, max_length=255)
    ports: list[int] = Field(min_length=1, max_length=MAX_SERVICE_ENUM_PORTS)
    probe_timeout_ms: int = Field(default=1000, ge=50, le=60_000)
    max_threads: int = Field(default=DEFAULT_SERVICEENUM_THREADS, ge=1, le=64)
    execution_target: str = "auto"
    source_scan_job_id: str | None = None

    @field_validator("host")
    @classmethod
    def validate_host(cls, value: str) -> str:
        return normalize_single_host(value.strip())

    @field_validator("ports")
    @classmethod
    def normalize_ports(cls, value: list[int]) -> list[int]:
        ports = sorted({validate_port_number(port) for port in value})
        if not ports:
            raise ValueError("At least one port is required")
        if len(ports) > MAX_SERVICE_ENUM_PORTS:
            raise ValueError(f"At most {MAX_SERVICE_ENUM_PORTS} ports are allowed")
        return ports

    @field_validator("execution_target")
    @classmethod
    def validate_execution_target(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized != "auto":
            raise ValueError("F0023 supports execution_target=auto only")
        return normalized

    @field_validator("source_scan_job_id")
    @classmethod
    def normalize_source_scan_job_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        try:
            uuid.UUID(normalized)
        except ValueError as exc:
            raise ValueError("source_scan_job_id must be a UUID") from exc
        return normalized


@dataclass(frozen=True)
class ServiceProbe:
    host: str
    port: int


@dataclass(frozen=True)
class FingerprintRule:
    service: str
    ports: tuple[int, ...] = ()
    banner_patterns: tuple[str, ...] = ()
    header_patterns: tuple[str, ...] = ()
    confidence: float = 0.45


FINGERPRINT_RULES: tuple[FingerprintRule, ...] = (
    FingerprintRule("ftp", (20, 21), (r"\bFTP\b", r"^220.*FileZilla", r"^220.*ProFTPD"), confidence=0.9),
    FingerprintRule("ssh", (22,), (r"^SSH-\d", r"OpenSSH", r"Dropbear"), confidence=0.95),
    FingerprintRule("telnet", (23,), (r"Telnet", r"login:"), confidence=0.75),
    FingerprintRule("smtp", (25, 465, 587), (r"^220.*SMTP", r"ESMTP", r"Postfix", r"Exim"), confidence=0.9),
    FingerprintRule("dns", (53,), confidence=0.45),
    FingerprintRule("dhcp", (67, 68), confidence=0.35),
    FingerprintRule("http", (80, 8000, 8001, 8008, 8080, 8081, 8888), header_patterns=(r"^server:",), confidence=0.9),
    FingerprintRule("kerberos", (88,), confidence=0.45),
    FingerprintRule("pop3", (110, 995), (r"^\+OK.*POP",), confidence=0.85),
    FingerprintRule("ntp", (123,), confidence=0.35),
    FingerprintRule("imap", (143, 993), (r"^\* OK.*IMAP",), confidence=0.85),
    FingerprintRule("snmp", (161, 162), confidence=0.35),
    FingerprintRule("ldap", (389,), confidence=0.45),
    FingerprintRule("https", (443, 8443, 9443), header_patterns=(r"^server:",), confidence=0.9),
    FingerprintRule("smb", (445,), confidence=0.45),
    FingerprintRule("ldaps", (636,), confidence=0.45),
    FingerprintRule("rsync", (873,), (r"^@RSYNCD",), confidence=0.9),
    FingerprintRule("ftps", (989, 990), confidence=0.45),
    FingerprintRule("imaps", (993,), confidence=0.45),
    FingerprintRule("pop3s", (995,), confidence=0.45),
    FingerprintRule("mssql", (1433,), confidence=0.45),
    FingerprintRule("oracle", (1521,), confidence=0.45),
    FingerprintRule("nfs", (2049,), confidence=0.45),
    FingerprintRule("mysql", (3306,), (r"mysql_native_password", r"MariaDB"), confidence=0.8),
    FingerprintRule("rdp", (3389,), confidence=0.45),
    FingerprintRule("postgresql", (5432,), confidence=0.45),
    FingerprintRule("vnc", (5900, 5901), (r"^RFB \d",), confidence=0.9),
    FingerprintRule("x11", (6000,), confidence=0.35),
    FingerprintRule("redis", (6379,), (r"^-NOAUTH", r"^\+PONG"), confidence=0.8),
    FingerprintRule("kubernetes", (6443, 10250, 10255), header_patterns=(r"kubernetes",), confidence=0.75),
    FingerprintRule("cassandra", (7000, 9042), confidence=0.45),
    FingerprintRule("zookeeper", (2181,), confidence=0.45),
    FingerprintRule("elasticsearch", (9200, 9300), header_patterns=(r"elastic",), confidence=0.75),
    FingerprintRule("memcached", (11211,), confidence=0.45),
    FingerprintRule("mongodb", (27017,), confidence=0.45),
    FingerprintRule("docker", (2375, 2376), header_patterns=(r"docker"), confidence=0.75),
    FingerprintRule("winrm", (5985, 5986), header_patterns=(r"Microsoft-HTTPAPI"), confidence=0.75),
    FingerprintRule("rabbitmq", (5672, 15672), header_patterns=(r"RabbitMQ"), confidence=0.75),
    FingerprintRule("mqtt", (1883, 8883), confidence=0.45),
    FingerprintRule("amqp", (5671, 5672), confidence=0.45),
    FingerprintRule("prometheus", (9090,), header_patterns=(r"prometheus"), confidence=0.7),
    FingerprintRule("grafana", (3000,), header_patterns=(r"grafana"), confidence=0.7),
    FingerprintRule("jenkins", (8080,), header_patterns=(r"Jenkins"), confidence=0.7),
    FingerprintRule("git", (9418,), confidence=0.45),
    FingerprintRule("subversion", (3690,), confidence=0.45),
    FingerprintRule("consul", (8500, 8600), header_patterns=(r"consul"), confidence=0.7),
    FingerprintRule("vault", (8200,), header_patterns=(r"vault"), confidence=0.7),
    FingerprintRule("splunk", (8000, 8089), header_patterns=(r"splunk"), confidence=0.7),
    FingerprintRule("neo4j", (7474, 7687), header_patterns=(r"neo4j"), confidence=0.7),
    FingerprintRule("couchdb", (5984,), header_patterns=(r"CouchDB"), confidence=0.75),
    FingerprintRule("influxdb", (8086,), header_patterns=(r"influx"), confidence=0.7),
    FingerprintRule("clickhouse", (8123, 9000), header_patterns=(r"ClickHouse"), confidence=0.75),
    FingerprintRule("sip", (5060, 5061), confidence=0.45),
    FingerprintRule("rtsp", (554, 8554), (r"^RTSP/",), confidence=0.85),
    FingerprintRule("irc", (6667, 6697), confidence=0.45),
    FingerprintRule("xmpp", (5222, 5269), confidence=0.45),
)


def normalized_serviceenum_args(raw_args: dict[str, Any]) -> dict[str, Any]:
    args = ServiceEnumArgs.model_validate(raw_args)
    return args.model_dump()


def estimate_serviceenum_progress_total(args: dict[str, Any]) -> int:
    return len(args["ports"])


def serviceenum_initial_state_counts() -> dict[str, int]:
    return {"error": 0, "identified": 0, "skipped": 0, "timeout": 0, "unknown": 0}


async def run_serviceenum_scan_job(
    app: Any,
    settings,
    scan_job_id: uuid.UUID,
    raw_args: dict[str, Any],
    started_at: float,
) -> ScanExecutionResult:
    args = ServiceEnumArgs.model_validate(raw_args)
    probes = [ServiceProbe(args.host, port) for port in args.ports]
    state_counts = serviceenum_initial_state_counts()
    all_results: list[dict[str, Any]] = []
    pending_results: list[dict[str, Any]] = []
    completed = 0
    sequence = 0
    semaphore = asyncio.Semaphore(args.max_threads)

    async def bounded_probe(probe: ServiceProbe) -> dict[str, Any]:
        async with semaphore:
            return await enumerate_service(probe.host, probe.port, timeout_ms=args.probe_timeout_ms)

    for future in asyncio.as_completed([bounded_probe(probe) for probe in probes]):
        result = await future
        completed += 1
        state_counts[result["status"]] = state_counts.get(result["status"], 0) + 1
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
    all_results.sort(key=lambda item: (item["host"], item["port"]))
    summary = {
        "duration_ms": duration_ms,
        "host": args.host,
        "identified_count": state_counts["identified"],
        "ports_enumerated": len(probes),
        "source_scan_job_id": args.source_scan_job_id,
        "state_counts": state_counts,
    }
    return ScanExecutionResult(
        results=all_results,
        summary=summary,
        state_counts=state_counts,
        probes_completed=len(probes),
        probes_total=len(probes),
        next_sequence=sequence + 1,
    )


async def enumerate_service(host: str, port: int, *, timeout_ms: int) -> dict[str, Any]:
    started = time.perf_counter()
    evidence: list[dict[str, Any]] = []
    tls: dict[str, Any] | None = None
    banner = ""
    headers: dict[str, str] = {}
    error: str | None = None
    try:
        open_state = await tcp_open_state(host, port, timeout_ms=timeout_ms)
        if open_state != "open":
            return service_finding(
                host,
                port,
                started,
                status="timeout" if open_state == "timeout" else "skipped",
                service_guess="unknown",
                confidence=0,
                evidence=[{"type": "tcp", "value": open_state}],
                error="Port did not accept a TCP connection.",
            )

        if port in TLS_PORT_HINTS:
            tls = await probe_tls_certificate(host, port, timeout_ms=timeout_ms)
            if tls is not None:
                evidence.append({"type": "tls.certificate", "value": tls.get("subject_cn") or tls.get("issuer_cn") or "present"})

        if port in HTTP_PORT_HINTS or tls is not None:
            headers = await probe_http_head(host, port, timeout_ms=timeout_ms, use_tls=tls is not None)
            if headers:
                evidence.append({"type": "http.response", "value": headers.get(":status", "HTTP response")})
                server = headers.get("server")
                if server:
                    evidence.append({"type": "http.server", "value": server})

        if not headers and tls is None:
            banner = await probe_passive_banner(host, port, timeout_ms=timeout_ms)
            if banner:
                evidence.append({"type": "banner", "value": banner[:160]})

        if not headers and not banner and tls is None:
            headers = await probe_http_head(host, port, timeout_ms=timeout_ms, use_tls=False)
            if headers:
                evidence.append({"type": "http.response", "value": headers.get(":status", "HTTP response")})
                server = headers.get("server")
                if server:
                    evidence.append({"type": "http.server", "value": server})

        service_guess, confidence, match_evidence = fingerprint_service(port, banner=banner, headers=headers, tls=tls)
        evidence.extend(match_evidence)
        status = "identified" if service_guess != "unknown" else "unknown"
    except TimeoutError:
        return service_finding(
            host,
            port,
            started,
            status="timeout",
            service_guess="unknown",
            confidence=0,
            evidence=evidence,
            error="Service probe timed out.",
        )
    except Exception as exc:
        service_guess = "unknown"
        confidence = 0
        status = "error"
        error = exc.__class__.__name__

    return service_finding(
        host,
        port,
        started,
        status=status,
        service_guess=service_guess,
        confidence=confidence,
        banner=banner,
        tls=tls,
        evidence=evidence,
        error=error,
    )


async def tcp_open_state(host: str, port: int, *, timeout_ms: int) -> str:
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout_ms / 1000)
        writer.close()
        with suppress(Exception):
            await writer.wait_closed()
        return "open"
    except TimeoutError:
        return "timeout"
    except (ConnectionRefusedError, ConnectionResetError):
        return "closed"
    except OSError:
        return "closed"


async def probe_passive_banner(host: str, port: int, *, timeout_ms: int) -> str:
    reader: asyncio.StreamReader | None = None
    writer: asyncio.StreamWriter | None = None
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout_ms / 1000)
        data = await asyncio.wait_for(reader.read(512), timeout=timeout_ms / 1000)
        return decode_banner(data)
    except TimeoutError:
        return ""
    finally:
        if writer is not None:
            writer.close()
            with suppress(Exception):
                await writer.wait_closed()


async def probe_http_head(host: str, port: int, *, timeout_ms: int, use_tls: bool) -> dict[str, str]:
    writer: asyncio.StreamWriter | None = None
    try:
        ssl_context = tls_client_context() if use_tls else None
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port, ssl=ssl_context, server_hostname=host if use_tls else None),
            timeout=timeout_ms / 1000,
        )
        request = (
            f"HEAD / HTTP/1.1\r\nHost: {host}\r\nUser-Agent: Xero-ServiceEnum/0.1\r\n"
            "Connection: close\r\nAccept: */*\r\n\r\n"
        )
        writer.write(request.encode("ascii"))
        await asyncio.wait_for(writer.drain(), timeout=timeout_ms / 1000)
        data = await asyncio.wait_for(reader.read(2048), timeout=timeout_ms / 1000)
        return parse_http_headers(data)
    except Exception:
        return {}
    finally:
        if writer is not None:
            writer.close()
            with suppress(Exception):
                await writer.wait_closed()


async def probe_tls_certificate(host: str, port: int, *, timeout_ms: int) -> dict[str, Any] | None:
    writer: asyncio.StreamWriter | None = None
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port, ssl=tls_client_context(), server_hostname=host),
            timeout=timeout_ms / 1000,
        )
        _ = reader
        ssl_object = writer.get_extra_info("ssl_object")
        if ssl_object is None:
            return None
        cert_der = ssl_object.getpeercert(binary_form=True)
        if not cert_der:
            return None
        return parse_tls_certificate(cert_der)
    except Exception:
        return None
    finally:
        if writer is not None:
            writer.close()
            with suppress(Exception):
                await writer.wait_closed()


def tls_client_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def parse_tls_certificate(cert_der: bytes) -> dict[str, Any]:
    cert = x509.load_der_x509_certificate(cert_der)
    sans: list[str] = []
    with suppress(x509.ExtensionNotFound):
        san_extension = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value
        sans.extend(san_extension.get_values_for_type(x509.DNSName))
        sans.extend(str(address) for address in san_extension.get_values_for_type(x509.IPAddress))
    not_after = getattr(cert, "not_valid_after_utc", None) or cert.not_valid_after.replace(tzinfo=UTC)
    not_before = getattr(cert, "not_valid_before_utc", None) or cert.not_valid_before.replace(tzinfo=UTC)
    return {
        "issuer_cn": common_name(cert.issuer),
        "not_after": not_after.isoformat(),
        "not_before": not_before.isoformat(),
        "sans": sans,
        "serial_number": str(cert.serial_number),
        "subject_cn": common_name(cert.subject),
    }


def common_name(name: x509.Name) -> str | None:
    values = name.get_attributes_for_oid(NameOID.COMMON_NAME)
    if not values:
        return None
    return values[0].value


def parse_http_headers(data: bytes) -> dict[str, str]:
    text = decode_banner(data)
    if not text.startswith("HTTP/"):
        return {}
    headers: dict[str, str] = {}
    lines = text.splitlines()
    if lines:
        headers[":status"] = lines[0].strip()
    for line in lines[1:]:
        if not line.strip():
            break
        name, separator, value = line.partition(":")
        if separator:
            headers[name.strip().lower()] = value.strip()
    return headers


def decode_banner(data: bytes) -> str:
    return data.decode("utf-8", errors="replace").replace("\x00", "").strip()


def fingerprint_service(
    port: int,
    *,
    banner: str,
    headers: dict[str, str],
    tls: dict[str, Any] | None,
) -> tuple[str, float, list[dict[str, Any]]]:
    evidence: list[dict[str, Any]] = []
    header_lines = [f"{key}: {value}" for key, value in headers.items()]
    if headers:
        service = "https" if tls is not None else "http"
        return service, 0.9, [{"type": "fingerprint", "value": "HTTP response headers"}]
    if banner.startswith("SSH-"):
        return "ssh", 0.95, [{"type": "fingerprint", "value": "SSH protocol banner"}]
    if tls is not None:
        return "https" if port in TLS_PORT_HINTS else "tls", 0.8, [{"type": "fingerprint", "value": "TLS certificate"}]

    for rule in FINGERPRINT_RULES:
        if any(re.search(pattern, banner, re.IGNORECASE) for pattern in rule.banner_patterns):
            return rule.service, rule.confidence, [{"type": "fingerprint", "value": f"{rule.service} banner"}]
        if any(
            re.search(pattern, header_line, re.IGNORECASE)
            for pattern in rule.header_patterns
            for header_line in header_lines
        ):
            return rule.service, rule.confidence, [{"type": "fingerprint", "value": f"{rule.service} header"}]

    for rule in FINGERPRINT_RULES:
        if port in rule.ports:
            evidence.append({"type": "port_hint", "value": rule.service})
            return rule.service, min(rule.confidence, 0.45), evidence
    return "unknown", 0, evidence


def service_finding(
    host: str,
    port: int,
    started: float,
    *,
    status: str,
    service_guess: str,
    confidence: float,
    banner: str = "",
    tls: dict[str, Any] | None = None,
    evidence: list[dict[str, Any]] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "banner": banner,
        "confidence": round(confidence, 2),
        "error": error,
        "evidence": evidence or [],
        "host": host,
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        "port": port,
        "service_guess": service_guess,
        "status": status,
        "tls": tls,
        "transport": "tcp",
    }
