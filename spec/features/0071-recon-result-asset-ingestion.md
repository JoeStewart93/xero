# F0071: Recon Result to Asset Ingestion

## Metadata
| Field | Value |
|---|---|
| ID | F0071 |
| Priority | P0 |
| Status | Planned |
| MVP Phase | 4 |
| Depends on | F0030, F0017 |

## Summary
Automatic asset creation and enrichment from reconnaissance scan results. Host discovery creates host assets, service discovery creates service assets, and vulnerability findings create vulnerability assets. Includes deduplication and relationship mapping.

## Requirements
- Automatic asset creation from scan results
- Deduplication by IP/domain
- Relationship mapping (host ? services ? vulnerabilities)
- Asset enrichment with scan metadata
- Integration with all recon modules

## Asset Types

| Source | Asset Type | Fields |
| :--- | :--- | :--- |
| Port Scan | Host | IP, hostname, OS, open_ports |
| Service Enum | Service | Port, protocol, service, version |
| Vuln Scan | Vulnerability | CVE, severity, description |
| DNS Enum | Domain | Domain name, nameservers |
| Whois | Domain | Registrar, creation_date, expiry |
| HTTP Enum | Web App | URL, technology, directories |
| Cloud Recon | Cloud Resource | Provider, type, ARN |

## Database Schema Extensions

`python
class ReconResult(BaseModel):
    __tablename__ = \"recon_results\"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    scan_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey(\"tasks.id\"), index=True)
    result_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  // host, service, vuln, domain
    target: Mapped[str] = mapped_column(String(512), nullable=False)  // IP, domain, or identifier
    data: Mapped[dict] = mapped_column(JSON, nullable=False)  // Full result data
    assets_created: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)  // List of asset IDs
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

class Asset(BaseModel):
    __tablename__ = \"assets\"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    asset_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  // host, service, domain, vuln, cloud
    identifier: Mapped[str] = mapped_column(String(512), nullable=False, unique=True, index=True)  // IP, domain, CVE
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)  // Asset metadata
    source: Mapped[str] = mapped_column(String(64), default=\"manual\", nullable=False)  // manual, beacon, recon_scan
    recon_result_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey(\"recon_results.id\"), nullable=True)
    parent_asset_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey(\"assets.id\"), nullable=True)
    related_assets: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)  // Child assets
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
`

## Result Processing Pipeline

`
Scan Result ? Parse Results ? Check Existing Assets ? Create/Update Assets ? Build Relationships ? Store ReconResult
`

## Asset Creation Logic

`python
async def ingest_recon_results(scan_id: uuid.UUID, results: dict) -> list[str]:
    \"\"\"Ingest recon scan results into asset inventory.\"\"\"
    asset_ids = []

    # Process host discoveries
    for host in results.get(\"hosts\", []):
        host_asset = await create_or_update_host_asset(host)
        asset_ids.append(host_asset.id)

    # Process service discoveries
    for service in results.get(\"services\", []):
        service_asset = await create_or_update_service_asset(service)
        asset_ids.append(service_asset.id)
        # Link to parent host
        await link_assets(service_asset.id, service[\"host_asset_id\"], \"parent\")

    # Process vulnerability discoveries
    for vuln in results.get(\"vulnerabilities\", []):
        vuln_asset = await create_or_update_vuln_asset(vuln)
        asset_ids.append(vuln_asset.id)
        # Link to affected service
        await link_assets(vuln_asset.id, vuln[\"service_asset_id\"], \"affects\")

    # Store recon result reference
    await store_recon_result(scan_id, results, asset_ids)

    return asset_ids

async def create_or_update_host_asset(host_data: dict) -> Asset:
    \"\"\"Create or update host asset.\"\"\"
    identifier = host_data.get(\"ip\") or host_data.get(\"hostname\")

    # Check for existing asset
    existing = await db.query(Asset).filter(
        Asset.identifier == identifier,
        Asset.asset_type == \"host\"
    ).first()

    if existing:
        # Update existing
        existing.data = merge_asset_data(existing.data, host_data)
        existing.last_updated = utc_now()
        return existing
    else:
        # Create new
        return await db.create(Asset(
            asset_type=\"host\",
            identifier=identifier,
            name=host_data.get(\"hostname\"),
            data=host_data,
            source=\"recon_scan\",
            tags=extract_tags(host_data),
        ))
`

## Relationship Mapping

`
Domain (example.com)
+-- Host (192.168.1.100)
�   +-- Service (HTTPS/443)
�   �   +-- Vulnerability (CVE-2021-44228)
�   +-- Service (SSH/22)
�   +-- Service (MySQL/3306)
+-- Host (192.168.1.101)
    +-- Service (HTTPS/443)
`

## Stages

### Stage 1: Asset Model Extensions
**Goal:** Extend asset models for recon integration.
**Acceptance Criteria:**
- [ ]
econ_results table created
- [ ] ssets table extended with source and relationships
- [ ] Alembic migration created
- [ ] Indexes added for performance

### Stage 2: Ingestion Pipeline
**Goal:** Implement result processing pipeline.
**Acceptance Criteria:**
- [ ] Result parsing for each recon type
- [ ] Asset creation/update logic
- [ ] Deduplication by identifier
- [ ] Relationship building

### Stage 3: Integration with Recon Modules
**Goal:** Wire up all recon modules to asset ingestion.
**Acceptance Criteria:**
- [ ] Port scan creates host assets
- [ ] Service enum creates service assets
- [ ] Vuln scan creates vulnerability assets
- [ ] DNS/whois creates domain assets
- [ ] Cloud recon creates cloud resource assets

### Stage 4: UI Integration
**Goal:** Display asset source and relationships.
**Acceptance Criteria:**
- [ ] Asset list shows source (recon vs manual)
- [ ] Asset detail shows relationships
- [ ] Recon result linked from asset

## Feature Acceptance Criteria

- [ ] Scan results auto-create assets
- [ ] Deduplication prevents duplicates
- [ ] Relationships preserved in asset graph
- [ ] UI shows asset source (recon vs manual)
- [ ] All recon modules integrated

## Test Plan

### Unit Tests
- [ ] test_asset_deduplication
- [ ] test_relationship_creation
- [ ] test_recon_result_storage
- [ ] test_asset_data_merging

### System / Integration Tests
- [ ] Port scan creates host assets
- [ ] Service enum links to host assets
- [ ] Vuln scan links to service assets
- [ ] Re-scanning updates existing assets
- [ ] Relationships queryable

### Playwright Tests
- [ ] Asset list shows source badges
- [ ] Asset detail shows parent/child relationships
- [ ] Recon result accessible from asset
- [ ] Network topology view uses asset relationships

---

*End of Document*
