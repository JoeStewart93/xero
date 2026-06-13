from __future__ import annotations

import ipaddress
import re
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session
from xero_common.models import utc_now

from xero_c2.models import Asset, AssetGroup, AssetGroupingEvent, AssetGroupingRule, AssetGroupMembership

ACTOR_ASSET_INGESTION = "system:asset-ingestion"
ACTOR_GROUPING_SYSTEM = "system:asset-grouping"
GROUP_SOURCE_AUTO = "auto"
GROUP_TYPE_AUTO = "auto"
HOST_ASSET_TYPES = {"beacon_host", "discovered_host"}
RULE_DOMAIN = "domain"
RULE_OS = "os"
RULE_SUBNET = "subnet"
SUPPORTED_RULE_KEYS = {RULE_DOMAIN, RULE_OS, RULE_SUBNET}

DEFAULT_RULES: dict[str, dict[str, Any]] = {
    RULE_SUBNET: {"enabled": True, "config": {"prefix_length": 24}},
    RULE_DOMAIN: {"enabled": True, "config": {"include_workgroups": True}},
    RULE_OS: {"enabled": True, "config": {"require_version": True}},
}


@dataclass(frozen=True)
class GroupingMatch:
    rule_key: str
    group_key: str
    name: str
    criterion_type: str
    criterion_value: str
    description: str
    metadata: dict[str, Any]


def ensure_default_grouping_rules(session: Session) -> dict[str, AssetGroupingRule]:
    rule_query = select(AssetGroupingRule).where(AssetGroupingRule.rule_key.in_(SUPPORTED_RULE_KEYS))
    existing = {
        rule.rule_key: rule
        for rule in session.execute(rule_query).scalars().all()
    }
    for rule_key, defaults in DEFAULT_RULES.items():
        if rule_key in existing:
            continue
        rule = AssetGroupingRule(
            rule_key=rule_key,
            enabled=bool(defaults["enabled"]),
            config=dict(defaults["config"]),
            version=1,
            updated_by=ACTOR_GROUPING_SYSTEM,
        )
        session.add(rule)
        existing[rule_key] = rule
    session.flush()
    return existing


def _enabled_rules(session: Session) -> dict[str, AssetGroupingRule]:
    return {key: rule for key, rule in ensure_default_grouping_rules(session).items() if rule.enabled}


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower().rstrip(".")
    return normalized or None


def _subnet_match(asset: Asset, rule: AssetGroupingRule) -> GroupingMatch | None:
    if not asset.primary_ip:
        return None
    try:
        ip_value = ipaddress.ip_address(asset.primary_ip)
    except ValueError:
        return None
    configured_prefix = int((rule.config or {}).get("prefix_length", 24))
    max_prefix = 32 if ip_value.version == 4 else 128
    prefix_length = min(max(configured_prefix, 0), max_prefix)
    network = ipaddress.ip_network(f"{ip_value}/{prefix_length}", strict=False)
    network_key = network.with_prefixlen
    return GroupingMatch(
        rule_key=RULE_SUBNET,
        group_key=f"subnet:{network_key}",
        name=f"Subnet {network_key}",
        criterion_type="subnet",
        criterion_value=network_key,
        description=f"Assets observed inside {network_key}",
        metadata={"ip_version": ip_value.version, "prefix_length": prefix_length},
    )


def _domain_or_workgroup_match(asset: Asset, rule: AssetGroupingRule) -> GroupingMatch | None:
    domain = _normalize_text(asset.domain)
    if domain:
        return GroupingMatch(
            rule_key=RULE_DOMAIN,
            group_key=f"domain:{domain}",
            name=f"Domain {domain}",
            criterion_type="domain",
            criterion_value=domain,
            description=f"Assets associated with {domain}",
            metadata={"domain": domain},
        )
    if not (rule.config or {}).get("include_workgroups", True):
        return None
    metadata = asset.asset_metadata or {}
    workgroup = _normalize_text(str(metadata.get("workgroup"))) if metadata.get("workgroup") else None
    if workgroup is None:
        return None
    return GroupingMatch(
        rule_key=RULE_DOMAIN,
        group_key=f"workgroup:{workgroup}",
        name=f"Workgroup {workgroup.upper()}",
        criterion_type="workgroup",
        criterion_value=workgroup,
        description=f"Assets explicitly observed in workgroup {workgroup.upper()}",
        metadata={"workgroup": workgroup},
    )


def _os_family_and_major(os_value: str | None) -> tuple[str, str, str] | None:
    normalized = _normalize_text(os_value)
    if normalized is None:
        return None
    family_aliases = (
        ("windows", "Windows"),
        ("ubuntu", "Ubuntu"),
        ("debian", "Debian"),
        ("centos", "CentOS"),
        ("red hat", "Red Hat"),
        ("rhel", "Red Hat"),
        ("fedora", "Fedora"),
        ("macos", "macOS"),
        ("mac os", "macOS"),
        ("darwin", "macOS"),
        ("linux", "Linux"),
    )
    family_key = normalized.split()[0]
    family_label = family_key.title()
    for prefix, label in family_aliases:
        if normalized.startswith(prefix):
            family_key = "redhat" if prefix in {"red hat", "rhel"} else label.lower().replace(" ", "")
            family_label = label
            break
    version_match = re.search(r"\b(\d{1,4})(?:\.\d+)?\b", normalized)
    if version_match is None:
        return None
    return family_key, family_label, version_match.group(1)


def _os_match(asset: Asset, rule: AssetGroupingRule) -> GroupingMatch | None:
    parsed = _os_family_and_major(asset.os)
    if parsed is None:
        return None
    family_key, family_label, major = parsed
    return GroupingMatch(
        rule_key=RULE_OS,
        group_key=f"os:{family_key}:{major}",
        name=f"{family_label} {major}",
        criterion_type="os",
        criterion_value=f"{family_key}:{major}",
        description=f"Assets reporting {family_label} major version {major}",
        metadata={"os_family": family_key, "os_version_major": major, "raw_os": asset.os},
    )


def classify_asset(asset: Asset, rules: dict[str, AssetGroupingRule] | None = None) -> list[GroupingMatch]:
    if asset.asset_type not in HOST_ASSET_TYPES:
        return []
    active_rules = rules or {}
    matches = [
        _subnet_match(asset, active_rules[RULE_SUBNET]) if RULE_SUBNET in active_rules else None,
        _domain_or_workgroup_match(asset, active_rules[RULE_DOMAIN]) if RULE_DOMAIN in active_rules else None,
        _os_match(asset, active_rules[RULE_OS]) if RULE_OS in active_rules else None,
    ]
    return [match for match in matches if match is not None]


def _record_event(
    session: Session,
    *,
    actor_subject: str,
    event_type: str,
    message: str,
    metadata: dict[str, Any] | None = None,
    asset_id: uuid.UUID | None = None,
    group_id: uuid.UUID | None = None,
    rule_id: uuid.UUID | None = None,
) -> AssetGroupingEvent:
    event = AssetGroupingEvent(
        actor_subject=actor_subject,
        asset_id=asset_id,
        event_type=event_type,
        event_metadata=metadata or {},
        group_id=group_id,
        message=message,
        occurred_at=utc_now(),
        rule_id=rule_id,
    )
    session.add(event)
    return event


def _upsert_group(session: Session, match: GroupingMatch, rule: AssetGroupingRule) -> tuple[AssetGroup, bool]:
    group = session.execute(select(AssetGroup).where(AssetGroup.group_key == match.group_key)).scalar_one_or_none()
    created = group is None
    if group is None:
        group = AssetGroup(
            criterion_type=match.criterion_type,
            criterion_value=match.criterion_value,
            description=match.description,
            group_key=match.group_key,
            group_metadata=match.metadata,
            group_type=GROUP_TYPE_AUTO,
            name=match.name,
            rule_id=rule.id,
        )
    else:
        group.criterion_type = match.criterion_type
        group.criterion_value = match.criterion_value
        group.description = match.description
        group.group_metadata = match.metadata
        group.group_type = GROUP_TYPE_AUTO
        group.name = match.name
        group.rule_id = rule.id
    session.add(group)
    session.flush()
    if created:
        _record_event(
            session,
            actor_subject=ACTOR_GROUPING_SYSTEM,
            event_type="grouping.group.created",
            group_id=group.id,
            message=f"Created auto group {group.name}",
            metadata={"group_key": group.group_key, "rule_key": match.rule_key},
            rule_id=rule.id,
        )
    return group, created


def sync_asset_group_memberships(
    session: Session,
    asset: Asset,
    *,
    actor_subject: str = ACTOR_ASSET_INGESTION,
    reason: str = "asset.updated",
    purge_disabled: bool = False,
) -> dict[str, int]:
    active_rules = _enabled_rules(session)
    matches = classify_asset(asset, active_rules)
    existing_memberships = session.execute(
        select(AssetGroupMembership).where(
            AssetGroupMembership.asset_id == asset.id,
            AssetGroupMembership.source == GROUP_SOURCE_AUTO,
        )
    ).scalars().all()
    existing_by_group_id = {membership.group_id: membership for membership in existing_memberships}
    desired_group_ids: set[uuid.UUID] = set()
    added = 0
    removed = 0
    touched = 0

    for match in matches:
        rule = active_rules[match.rule_key]
        group, _created = _upsert_group(session, match, rule)
        desired_group_ids.add(group.id)
        membership = existing_by_group_id.get(group.id)
        if membership is None:
            membership = AssetGroupMembership(
                asset_id=asset.id,
                group_id=group.id,
                source=GROUP_SOURCE_AUTO,
                rule_id=rule.id,
                first_seen=utc_now(),
                last_seen=utc_now(),
                membership_metadata={"reason": reason, "rule_key": match.rule_key},
            )
            session.add(membership)
            added += 1
            _record_event(
                session,
                actor_subject=actor_subject,
                asset_id=asset.id,
                event_type="grouping.membership.added",
                group_id=group.id,
                message=f"Added {asset.display_name} to {group.name}",
                metadata={"group_key": group.group_key, "reason": reason, "rule_key": match.rule_key},
                rule_id=rule.id,
            )
        else:
            membership.rule_id = rule.id
            membership.last_seen = utc_now()
            membership.membership_metadata = {"reason": reason, "rule_key": match.rule_key}
            session.add(membership)
            touched += 1

    enabled_rule_ids = {rule.id for rule in active_rules.values()}
    for membership in existing_memberships:
        if membership.group_id in desired_group_ids:
            continue
        should_remove = membership.rule_id in enabled_rule_ids or purge_disabled
        if not should_remove:
            continue
        group = session.get(AssetGroup, membership.group_id)
        _record_event(
            session,
            actor_subject=actor_subject,
            asset_id=asset.id,
            event_type="grouping.membership.removed",
            group_id=membership.group_id,
            message=f"Removed {asset.display_name} from {group.name if group else 'auto group'}",
            metadata={"reason": reason},
            rule_id=membership.rule_id,
        )
        session.delete(membership)
        removed += 1

    session.flush()
    return {"added": added, "removed": removed, "touched": touched}


def sync_assets_group_memberships(
    session: Session,
    assets: list[Asset],
    *,
    actor_subject: str = ACTOR_ASSET_INGESTION,
    reason: str = "assets.updated",
    purge_disabled: bool = False,
) -> dict[str, int]:
    seen: set[uuid.UUID] = set()
    summary = {"added": 0, "assets_processed": 0, "removed": 0, "touched": 0}
    for asset in assets:
        if asset.id in seen:
            continue
        seen.add(asset.id)
        result = sync_asset_group_memberships(
            session,
            asset,
            actor_subject=actor_subject,
            purge_disabled=purge_disabled,
            reason=reason,
        )
        summary["assets_processed"] += 1
        summary["added"] += result["added"]
        summary["removed"] += result["removed"]
        summary["touched"] += result["touched"]
    return summary


def rerun_grouping(
    session: Session,
    *,
    actor_subject: str,
    purge_disabled: bool = False,
) -> dict[str, int]:
    assets = session.execute(select(Asset).where(Asset.asset_type.in_(HOST_ASSET_TYPES))).scalars().all()
    summary = sync_assets_group_memberships(
        session,
        assets,
        actor_subject=actor_subject,
        purge_disabled=purge_disabled,
        reason="grouping.rerun",
    )
    _record_event(
        session,
        actor_subject=actor_subject,
        event_type="grouping.rerun.completed",
        message="Completed automatic asset grouping rerun",
        metadata={**summary, "purge_disabled": purge_disabled},
    )
    return summary


def update_grouping_rules(
    session: Session,
    updates: list[dict[str, Any]],
    *,
    actor_subject: str,
    purge_disabled: bool = False,
    rerun: bool = True,
) -> tuple[list[AssetGroupingRule], dict[str, int] | None]:
    rules = ensure_default_grouping_rules(session)
    updated_rules: list[AssetGroupingRule] = []
    for update in updates:
        rule_key = update["rule_key"]
        if rule_key not in SUPPORTED_RULE_KEYS:
            raise ValueError(f"Unsupported grouping rule: {rule_key}")
        rule = rules[rule_key]
        changed = False
        if "enabled" in update and update["enabled"] is not None and rule.enabled != update["enabled"]:
            rule.enabled = bool(update["enabled"])
            changed = True
        if "config" in update and update["config"] is not None and rule.config != update["config"]:
            rule.config = dict(update["config"])
            changed = True
        if changed:
            rule.version += 1
            rule.updated_by = actor_subject
            session.add(rule)
            _record_event(
                session,
                actor_subject=actor_subject,
                event_type="grouping.rule.updated",
                message=f"Updated grouping rule {rule.rule_key}",
                metadata={"enabled": rule.enabled, "config": rule.config, "version": rule.version},
                rule_id=rule.id,
            )
        updated_rules.append(rule)
    session.flush()
    summary = rerun_grouping(session, actor_subject=actor_subject, purge_disabled=purge_disabled) if rerun else None
    return updated_rules, summary


def _public_rule(rule: AssetGroupingRule) -> dict[str, Any]:
    return {
        "id": str(rule.id),
        "rule_key": rule.rule_key,
        "enabled": rule.enabled,
        "config": rule.config or {},
        "version": rule.version,
        "updated_by": rule.updated_by,
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
    }


def list_grouping_rule_payloads(session: Session) -> list[dict[str, Any]]:
    rules = ensure_default_grouping_rules(session)
    return [_public_rule(rules[rule_key]) for rule_key in sorted(SUPPORTED_RULE_KEYS)]


def public_group(session: Session, group: AssetGroup) -> dict[str, Any]:
    member_count = session.execute(
        select(func.count()).select_from(AssetGroupMembership).where(AssetGroupMembership.group_id == group.id)
    ).scalar_one()
    return {
        "id": str(group.id),
        "group_key": group.group_key,
        "name": group.name,
        "description": group.description,
        "type": group.group_type,
        "rule_id": str(group.rule_id) if group.rule_id else None,
        "criterion_type": group.criterion_type,
        "criterion_value": group.criterion_value,
        "parent_id": str(group.parent_id) if group.parent_id else None,
        "metadata": group.group_metadata or {},
        "member_count": int(member_count),
        "created_at": group.created_at,
        "updated_at": group.updated_at,
    }


def list_group_payloads(
    session: Session,
    *,
    group_type: str | None = GROUP_TYPE_AUTO,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    filters = []
    if group_type:
        filters.append(AssetGroup.group_type == group_type)
    if q:
        query = q.strip()
        if query:
            pattern = f"%{query}%"
            filters.append(
                or_(
                    AssetGroup.name.ilike(pattern),
                    AssetGroup.group_key.ilike(pattern),
                    AssetGroup.criterion_value.ilike(pattern),
                )
            )
    count_query = select(func.count()).select_from(AssetGroup)
    item_query = select(AssetGroup).order_by(AssetGroup.name.asc()).offset(offset).limit(limit)
    for condition in filters:
        count_query = count_query.where(condition)
        item_query = item_query.where(condition)
    total = session.execute(count_query).scalar_one()
    groups = session.execute(item_query).scalars().all()
    return [public_group(session, group) for group in groups], int(total)


def asset_group_summaries(session: Session, asset_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = session.execute(
        select(AssetGroup, AssetGroupMembership)
        .join(AssetGroupMembership, AssetGroupMembership.group_id == AssetGroup.id)
        .where(AssetGroupMembership.asset_id == asset_id)
        .order_by(AssetGroup.name.asc())
    ).all()
    return [
        {
            "id": str(group.id),
            "group_key": group.group_key,
            "name": group.name,
            "type": group.group_type,
            "criterion_type": group.criterion_type,
            "criterion_value": group.criterion_value,
            "source": membership.source,
        }
        for group, membership in rows
    ]


def remove_feature_smoke_groups(session: Session, prefixes: list[str]) -> None:
    conditions = [AssetGroup.group_key.ilike(f"{prefix}%") for prefix in prefixes]
    if not conditions:
        return
    group_ids = select(AssetGroup.id).where(or_(*conditions))
    session.execute(delete(AssetGroupMembership).where(AssetGroupMembership.group_id.in_(group_ids)))
    session.execute(delete(AssetGroupingEvent).where(AssetGroupingEvent.group_id.in_(group_ids)))
    session.execute(delete(AssetGroup).where(AssetGroup.id.in_(group_ids)))
