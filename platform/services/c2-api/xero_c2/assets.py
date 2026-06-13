from __future__ import annotations

import ipaddress
import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from xero_common.models import utc_now

from xero_c2.asset_grouping import asset_group_summaries
from xero_c2.models import (
    Asset,
    AssetBeaconLink,
    AssetGroupMembership,
    AssetIdentifier,
    AssetObservation,
    AssetRelationship,
    Beacon,
    ScanJob,
    ScanResultChunk,
)

ASSET_SOURCE_BEACON = "beacon"
ASSET_SOURCE_SCAN = "scan"
ASSET_TYPE_BEACON_HOST = "beacon_host"
ASSET_TYPE_DISCOVERED_HOST = "discovered_host"
ASSET_TYPE_SERVICE = "service"
IDENTIFIER_BEACON_FINGERPRINT = "beacon_fingerprint"
IDENTIFIER_HOSTNAME = "hostname"
IDENTIFIER_IP = "ip"
IDENTIFIER_SERVICE_ENDPOINT = "service_endpoint"
RELATIONSHIP_EXPOSES_SERVICE = "exposes_service"


def normalize_ip(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return None


def normalize_hostname(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower().rstrip(".")
    return normalized or None


def _normalize_identifier(kind: str, value: str) -> str:
    if kind == IDENTIFIER_IP:
        return normalize_ip(value) or value.strip().lower()
    if kind in {IDENTIFIER_HOSTNAME, IDENTIFIER_SERVICE_ENDPOINT, IDENTIFIER_BEACON_FINGERPRINT}:
        return value.strip().lower()
    return value.strip()


def _domain_from_hostname(hostname: str | None) -> str | None:
    normalized = normalize_hostname(hostname)
    if normalized is None or "." not in normalized:
        return None
    return normalized.partition(".")[2] or None


def _find_asset_by_identifier(session: Session, kind: str, value: str | None) -> Asset | None:
    if not value:
        return None
    normalized = _normalize_identifier(kind, value)
    identifier = session.execute(
        select(AssetIdentifier)
        .where(AssetIdentifier.kind == kind, AssetIdentifier.normalized_value == normalized)
        .order_by(AssetIdentifier.created_at.asc())
        .limit(1)
    ).scalar_one_or_none()
    if identifier is None:
        return None
    return session.get(Asset, identifier.asset_id)


def _find_asset_by_dedup_key(session: Session, dedup_key: str) -> Asset | None:
    return session.execute(select(Asset).where(Asset.dedup_key == dedup_key)).scalar_one_or_none()


def _upsert_identifier(
    session: Session,
    asset: Asset,
    *,
    kind: str,
    value: str | None,
    source: str,
) -> AssetIdentifier | None:
    if value is None:
        return None
    normalized = _normalize_identifier(kind, value)
    if not normalized:
        return None
    session.flush()
    now = utc_now()
    identifier = session.execute(
        select(AssetIdentifier).where(
            AssetIdentifier.asset_id == asset.id,
            AssetIdentifier.kind == kind,
            AssetIdentifier.normalized_value == normalized,
        )
    ).scalar_one_or_none()
    if identifier is None:
        identifier = AssetIdentifier(
            asset_id=asset.id,
            kind=kind,
            value=value,
            normalized_value=normalized,
            source=source,
            first_seen=now,
            last_seen=now,
        )
    else:
        identifier.value = value
        identifier.source = source
        identifier.last_seen = now
    session.add(identifier)
    return identifier


def _record_observation(
    session: Session,
    asset: Asset,
    *,
    observation_type: str,
    payload: dict[str, Any],
    source: str,
    beacon_id: uuid.UUID | None = None,
    scan_job_id: uuid.UUID | None = None,
    scan_result_chunk_id: uuid.UUID | None = None,
) -> AssetObservation:
    session.flush()
    observation = AssetObservation(
        asset_id=asset.id,
        source=source,
        observation_type=observation_type,
        payload=payload,
        beacon_id=beacon_id,
        scan_job_id=scan_job_id,
        scan_result_chunk_id=scan_result_chunk_id,
        observed_at=utc_now(),
    )
    session.add(observation)
    return observation


def _upsert_host_asset(
    session: Session,
    *,
    host: str,
    source: str,
    hostname: str | None = None,
    os_name: str | None = None,
    preferred_type: str = ASSET_TYPE_DISCOVERED_HOST,
) -> Asset:
    ip_value = normalize_ip(host)
    normalized_hostname = normalize_hostname(hostname if hostname is not None else (None if ip_value else host))
    lookup_asset = _find_asset_by_identifier(session, IDENTIFIER_IP, ip_value)
    if lookup_asset is None and normalized_hostname is not None:
        lookup_asset = _find_asset_by_identifier(session, IDENTIFIER_HOSTNAME, normalized_hostname)

    if lookup_asset is None:
        if ip_value:
            dedup_key = f"host:ip:{ip_value}"
            display_name = normalized_hostname or ip_value
        else:
            dedup_key = f"host:name:{normalized_hostname or host.strip().lower()}"
            display_name = normalized_hostname or host.strip()
        lookup_asset = _find_asset_by_dedup_key(session, dedup_key)

    now = utc_now()
    if lookup_asset is None:
        lookup_asset = Asset(
            asset_type=preferred_type,
            source=source,
            dedup_key=dedup_key,
            display_name=display_name,
            hostname=normalized_hostname,
            domain=_domain_from_hostname(normalized_hostname),
            primary_ip=ip_value,
            os=os_name,
            first_seen=now,
            last_seen=now,
            asset_metadata={},
        )
    else:
        lookup_asset.last_seen = now
        if preferred_type == ASSET_TYPE_BEACON_HOST:
            lookup_asset.asset_type = ASSET_TYPE_BEACON_HOST
        if source == ASSET_SOURCE_BEACON:
            lookup_asset.source = ASSET_SOURCE_BEACON
        if normalized_hostname:
            lookup_asset.hostname = normalized_hostname
            lookup_asset.domain = _domain_from_hostname(normalized_hostname)
            lookup_asset.display_name = normalized_hostname
        if ip_value:
            lookup_asset.primary_ip = ip_value
            if not lookup_asset.display_name:
                lookup_asset.display_name = ip_value
        if os_name:
            lookup_asset.os = os_name
    session.add(lookup_asset)
    session.flush()
    _upsert_identifier(session, lookup_asset, kind=IDENTIFIER_IP, value=ip_value, source=source)
    _upsert_identifier(session, lookup_asset, kind=IDENTIFIER_HOSTNAME, value=normalized_hostname, source=source)
    return lookup_asset


def upsert_beacon_asset(session: Session, beacon: Beacon) -> Asset:
    fingerprint = beacon.machine_fingerprint_hash
    dedup_key = f"beacon:{fingerprint.lower()}"
    link = session.execute(
        select(AssetBeaconLink).where(AssetBeaconLink.machine_fingerprint_hash == fingerprint)
    ).scalar_one_or_none()
    asset = session.get(Asset, link.asset_id) if link is not None else None
    if asset is None:
        asset = _find_asset_by_dedup_key(session, dedup_key)
    if asset is None:
        asset = _find_asset_by_identifier(session, IDENTIFIER_IP, normalize_ip(beacon.internal_ip))
    if asset is None:
        asset = _find_asset_by_identifier(session, IDENTIFIER_HOSTNAME, beacon.hostname)

    now = utc_now()
    if asset is None:
        asset = Asset(
            asset_type=ASSET_TYPE_BEACON_HOST,
            source=ASSET_SOURCE_BEACON,
            dedup_key=dedup_key,
            display_name=normalize_hostname(beacon.hostname) or beacon.internal_ip,
            hostname=normalize_hostname(beacon.hostname),
            domain=_domain_from_hostname(beacon.hostname),
            primary_ip=normalize_ip(beacon.internal_ip),
            os=beacon.os,
            role="beacon",
            first_seen=now,
            last_seen=now,
            asset_metadata={"architecture": beacon.architecture, "pid": beacon.pid},
        )
    else:
        asset.asset_type = ASSET_TYPE_BEACON_HOST
        asset.source = ASSET_SOURCE_BEACON
        asset.dedup_key = dedup_key
        asset.display_name = normalize_hostname(beacon.hostname) or normalize_ip(beacon.internal_ip) or beacon.hostname
        asset.hostname = normalize_hostname(beacon.hostname)
        asset.domain = _domain_from_hostname(beacon.hostname)
        asset.primary_ip = normalize_ip(beacon.internal_ip)
        asset.os = beacon.os
        asset.role = "beacon"
        asset.last_seen = now
        asset.asset_metadata = {
            **(asset.asset_metadata or {}),
            "architecture": beacon.architecture,
            "external_ip": normalize_ip(beacon.external_ip),
            "pid": beacon.pid,
            "status": beacon.status,
            "transport_mode": beacon.transport_mode,
        }
    session.add(asset)
    session.flush()

    if link is None:
        link = session.execute(
            select(AssetBeaconLink).where(AssetBeaconLink.beacon_id == beacon.id)
        ).scalar_one_or_none()
    if link is None:
        link = AssetBeaconLink(
            asset_id=asset.id,
            beacon_id=beacon.id,
            machine_fingerprint_hash=fingerprint,
            first_seen=now,
            last_seen=now,
        )
    else:
        link.asset_id = asset.id
        link.beacon_id = beacon.id
        link.machine_fingerprint_hash = fingerprint
        link.last_seen = now
    session.add(link)

    _upsert_identifier(
        session,
        asset,
        kind=IDENTIFIER_BEACON_FINGERPRINT,
        value=fingerprint,
        source=ASSET_SOURCE_BEACON,
    )
    _upsert_identifier(session, asset, kind=IDENTIFIER_HOSTNAME, value=beacon.hostname, source=ASSET_SOURCE_BEACON)
    _upsert_identifier(session, asset, kind=IDENTIFIER_IP, value=beacon.internal_ip, source=ASSET_SOURCE_BEACON)
    _upsert_identifier(session, asset, kind=IDENTIFIER_IP, value=beacon.external_ip, source=ASSET_SOURCE_BEACON)
    _record_observation(
        session,
        asset,
        observation_type="beacon.registered",
        payload={
            "architecture": beacon.architecture,
            "hostname": beacon.hostname,
            "internal_ip": beacon.internal_ip,
            "os": beacon.os,
            "pid": beacon.pid,
            "status": beacon.status,
        },
        source=ASSET_SOURCE_BEACON,
        beacon_id=beacon.id,
    )
    return asset


def _upsert_service_asset(session: Session, host_asset: Asset, record: dict[str, Any], job: ScanJob) -> Asset:
    host = str(record.get("host") or host_asset.primary_ip or host_asset.display_name)
    port = int(record.get("port") or 0)
    transport = str(record.get("transport") or "tcp").lower()
    endpoint_host = normalize_ip(host) or normalize_hostname(host) or host.strip().lower()
    endpoint = f"{transport}://{endpoint_host}:{port}"
    service_guess = str(record.get("service_guess") or "unknown")
    asset = _find_asset_by_identifier(session, IDENTIFIER_SERVICE_ENDPOINT, endpoint)
    now = utc_now()
    if asset is None:
        asset = Asset(
            asset_type=ASSET_TYPE_SERVICE,
            source=ASSET_SOURCE_SCAN,
            dedup_key=f"service:{endpoint}",
            display_name=f"{service_guess} on {endpoint_host}:{port}",
            hostname=host_asset.hostname,
            domain=host_asset.domain,
            primary_ip=host_asset.primary_ip or normalize_ip(host),
            role=service_guess,
            first_seen=now,
            last_seen=now,
            asset_metadata={},
        )
    else:
        asset.last_seen = now
        asset.display_name = f"{service_guess} on {endpoint_host}:{port}"
        asset.hostname = host_asset.hostname
        asset.domain = host_asset.domain
        asset.primary_ip = host_asset.primary_ip or normalize_ip(host)
        asset.role = service_guess
    asset.asset_metadata = {
        **(asset.asset_metadata or {}),
        "banner": record.get("banner"),
        "confidence": record.get("confidence"),
        "port": port,
        "service_guess": service_guess,
        "status": record.get("status"),
        "transport": transport,
        "tls": record.get("tls"),
    }
    session.add(asset)
    session.flush()
    _upsert_identifier(session, asset, kind=IDENTIFIER_SERVICE_ENDPOINT, value=endpoint, source=ASSET_SOURCE_SCAN)
    _record_observation(
        session,
        asset,
        observation_type="scan.serviceenum",
        payload={"module": job.module, "record": record},
        source=ASSET_SOURCE_SCAN,
        scan_job_id=job.id,
    )
    return asset


def _upsert_relationship(
    session: Session,
    source_asset: Asset,
    target_asset: Asset,
    *,
    relationship_type: str,
    scan_job_id: uuid.UUID,
    metadata: dict[str, Any],
) -> AssetRelationship:
    session.flush()
    relationship = session.execute(
        select(AssetRelationship).where(
            AssetRelationship.source_asset_id == source_asset.id,
            AssetRelationship.target_asset_id == target_asset.id,
            AssetRelationship.relationship_type == relationship_type,
            AssetRelationship.scan_job_id == scan_job_id,
        )
    ).scalar_one_or_none()
    now = utc_now()
    if relationship is None:
        relationship = AssetRelationship(
            source_asset_id=source_asset.id,
            target_asset_id=target_asset.id,
            relationship_type=relationship_type,
            source=ASSET_SOURCE_SCAN,
            scan_job_id=scan_job_id,
            relationship_metadata=metadata,
            first_seen=now,
            last_seen=now,
        )
    else:
        relationship.relationship_metadata = metadata
        relationship.last_seen = now
    session.add(relationship)
    return relationship


def ingest_scan_assets(session: Session, job: ScanJob, summary_chunk: ScanResultChunk) -> list[Asset]:
    from xero_c2.portscan import PORTSCAN_MODULE_ID
    from xero_c2.serviceenum import SERVICEENUM_MODULE_ID

    ingested: list[Asset] = []
    if job.module == PORTSCAN_MODULE_ID:
        for record in job.results or []:
            host = record.get("host")
            if not host:
                continue
            asset = _upsert_host_asset(session, host=str(host), source=ASSET_SOURCE_SCAN)
            if record.get("state") == "open" and record.get("port") is not None:
                ports = set((asset.asset_metadata or {}).get("open_ports", []))
                ports.add(int(record["port"]))
                asset.asset_metadata = {**(asset.asset_metadata or {}), "open_ports": sorted(ports)}
            _record_observation(
                session,
                asset,
                observation_type="scan.portscan",
                payload={"module": job.module, "record": record},
                source=ASSET_SOURCE_SCAN,
                scan_job_id=job.id,
                scan_result_chunk_id=summary_chunk.id,
            )
            ingested.append(asset)
    elif job.module == SERVICEENUM_MODULE_ID:
        for record in job.results or []:
            host = record.get("host")
            port = record.get("port")
            if not host or port is None:
                continue
            host_asset = _upsert_host_asset(session, host=str(host), source=ASSET_SOURCE_SCAN)
            service_asset = _upsert_service_asset(session, host_asset, record, job)
            _upsert_relationship(
                session,
                host_asset,
                service_asset,
                relationship_type=RELATIONSHIP_EXPOSES_SERVICE,
                scan_job_id=job.id,
                metadata={"port": int(port), "transport": record.get("transport", "tcp")},
            )
            ingested.extend([host_asset, service_asset])
    return ingested


def _public_identifier(identifier: AssetIdentifier) -> dict[str, Any]:
    return {
        "id": str(identifier.id),
        "kind": identifier.kind,
        "value": identifier.value,
        "normalized_value": identifier.normalized_value,
        "source": identifier.source,
        "first_seen": identifier.first_seen,
        "last_seen": identifier.last_seen,
    }


def _public_beacon_link(session: Session, link: AssetBeaconLink) -> dict[str, Any]:
    beacon = session.get(Beacon, link.beacon_id)
    return {
        "id": str(link.id),
        "beacon_id": str(link.beacon_id),
        "hostname": beacon.hostname if beacon else None,
        "machine_fingerprint_hash": link.machine_fingerprint_hash,
        "status": beacon.status if beacon else None,
        "first_seen": link.first_seen,
        "last_seen": link.last_seen,
    }


def _public_relationship(session: Session, relationship: AssetRelationship, asset_id: uuid.UUID) -> dict[str, Any]:
    is_outbound = relationship.source_asset_id == asset_id
    related_id = relationship.target_asset_id if is_outbound else relationship.source_asset_id
    related_asset = session.get(Asset, related_id)
    return {
        "id": str(relationship.id),
        "asset_id": str(asset_id),
        "direction": "outbound" if is_outbound else "inbound",
        "related_asset_id": str(related_id),
        "related_asset_name": related_asset.display_name if related_asset else None,
        "relationship_type": relationship.relationship_type,
        "source": relationship.source,
        "scan_job_id": str(relationship.scan_job_id) if relationship.scan_job_id else None,
        "metadata": relationship.relationship_metadata or {},
        "first_seen": relationship.first_seen,
        "last_seen": relationship.last_seen,
    }


def _public_observation(observation: AssetObservation) -> dict[str, Any]:
    return {
        "id": str(observation.id),
        "source": observation.source,
        "observation_type": observation.observation_type,
        "payload": observation.payload or {},
        "beacon_id": str(observation.beacon_id) if observation.beacon_id else None,
        "scan_job_id": str(observation.scan_job_id) if observation.scan_job_id else None,
        "scan_result_chunk_id": str(observation.scan_result_chunk_id) if observation.scan_result_chunk_id else None,
        "observed_at": observation.observed_at,
    }


def public_asset(asset: Asset, session: Session, *, include_detail: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": str(asset.id),
        "asset_type": asset.asset_type,
        "source": asset.source,
        "display_name": asset.display_name,
        "hostname": asset.hostname,
        "domain": asset.domain,
        "primary_ip": asset.primary_ip,
        "os": asset.os,
        "role": asset.role,
        "first_seen": asset.first_seen,
        "last_seen": asset.last_seen,
        "metadata": asset.asset_metadata or {},
        "created_at": asset.created_at,
        "updated_at": asset.updated_at,
    }
    if not include_detail:
        return payload

    identifiers = session.execute(
        select(AssetIdentifier)
        .where(AssetIdentifier.asset_id == asset.id)
        .order_by(AssetIdentifier.kind.asc(), AssetIdentifier.last_seen.desc())
    ).scalars()
    links = session.execute(
        select(AssetBeaconLink)
        .where(AssetBeaconLink.asset_id == asset.id)
        .order_by(AssetBeaconLink.last_seen.desc())
    ).scalars()
    relationships = session.execute(
        select(AssetRelationship)
        .where(or_(AssetRelationship.source_asset_id == asset.id, AssetRelationship.target_asset_id == asset.id))
        .order_by(AssetRelationship.last_seen.desc())
        .limit(50)
    ).scalars()
    observations = session.execute(
        select(AssetObservation)
        .where(AssetObservation.asset_id == asset.id)
        .order_by(AssetObservation.observed_at.desc())
        .limit(25)
    ).scalars()
    payload.update(
        {
            "identifiers": [_public_identifier(identifier) for identifier in identifiers],
            "linked_beacons": [_public_beacon_link(session, link) for link in links],
            "relationships": [_public_relationship(session, relationship, asset.id) for relationship in relationships],
            "observations": [_public_observation(observation) for observation in observations],
            "groups": asset_group_summaries(session, asset.id),
        }
    )
    return payload


def list_asset_payloads(
    session: Session,
    *,
    asset_type: str | None = None,
    source: str | None = None,
    group_id: uuid.UUID | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    filters = []
    if asset_type:
        filters.append(Asset.asset_type == asset_type)
    if source:
        filters.append(Asset.source == source)
    if group_id:
        group_assets = select(AssetGroupMembership.asset_id).where(AssetGroupMembership.group_id == group_id)
        filters.append(Asset.id.in_(group_assets))
    if q:
        normalized_query = q.strip()
        if normalized_query:
            pattern = f"%{normalized_query}%"
            identifier_matches = select(AssetIdentifier.asset_id).where(
                or_(
                    AssetIdentifier.value.ilike(pattern),
                    AssetIdentifier.normalized_value.ilike(pattern),
                )
            )
            filters.append(
                or_(
                    Asset.display_name.ilike(pattern),
                    Asset.hostname.ilike(pattern),
                    Asset.domain.ilike(pattern),
                    Asset.primary_ip.ilike(pattern),
                    Asset.os.ilike(pattern),
                    Asset.id.in_(identifier_matches),
                )
            )

    count_query = select(func.count()).select_from(Asset)
    item_query = select(Asset).order_by(Asset.last_seen.desc(), Asset.display_name.asc()).offset(offset).limit(limit)
    for condition in filters:
        count_query = count_query.where(condition)
        item_query = item_query.where(condition)
    total = session.execute(count_query).scalar_one()
    items = session.execute(item_query).scalars().all()
    return [public_asset(asset, session) for asset in items], int(total)


def get_asset_payload(session: Session, asset_id: uuid.UUID) -> dict[str, Any] | None:
    asset = session.get(Asset, asset_id)
    if asset is None:
        return None
    return public_asset(asset, session, include_detail=True)
