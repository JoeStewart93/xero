# Xero UI Architecture and Information Design

**Version:** 1.1.0
**Date:** June 10, 2026
**Status:** Draft - Shell Refactor Baseline
**Purpose:** Define the operator UI structure, navigation hierarchy, and stubbed shell surfaces for the Xero C2 platform.

---

## 1. Executive Summary

Xero's UI is a project-scoped operator console for a local UI/BFF stack connected to a local or remote C2 backend. The interface must support high-density operational workflows without turning planned features into implied functionality.

The current refactor target is a shell-first implementation: add side sections, top tabs, and modal/side-panel scaffolding that future features can fill in later.

### Design Principles

1. **Project-centric:** Operational actions resolve against one active project at a time.
2. **Context-aware:** Surfaces show C2-required and project-required states instead of hiding planned work.
3. **Workflow-oriented:** Recon, beacons, exploits, payloads, assets, reports, and loot should feel connected.
4. **Dense and readable:** Prefer tables, split panes, compact toolbars, and scrollable lists over card-heavy layouts.
5. **Realtime-ready:** Status, beacon state, worker state, and activity feeds should be designed for WebSocket updates.
6. **Stitch-first:** UI planning and implementation must start in Stitch MCP before React/CSS edits.

### 2.0 Authentication and Route Guards (F0074)

The UI supports two login modes:

| Mode | When | Auth target | Session scope |
|---|---|---|---|
| Bootstrap | No C2 URL configured | BFF `POST /auth/login` | Settings (C2 URL), BFF `/health` |
| C2 operator | C2 URL configured (env or stored) | C2 `POST /api/v1/auth/login` | All operational C2-backed routes |

Route guard matrix:

| Route group | Bootstrap session | C2 operator session |
|---|---|---|
| `/settings` (C2 URL) | Allowed | Allowed |
| `/health` (BFF) | Allowed | Allowed (with bootstrap or after C2 login) |
| `/beacons`, `/settings/infrastructure`, Recon ops, etc. | Blocked (`C2RequiredPanel` or redirect) | Allowed |
| `/settings/access` (user management) | Blocked | C2 admin only (F0105) |

Settings Infrastructure panel shows worker inventory, protocol status, and transport status. There is no C2 connect password field after F0074; operator login establishes the C2 session.

---

## 2. Current State

### 2.1 Implemented Navigation

Current implemented primary navigation before this shell refactor:

| Area | Status | Notes |
|---|---:|---|
| Home | Implemented | Overview, C2/BFF status, realtime counts |
| Projects | Implemented | Local project/scope management |
| Recon | Basic | Tool queue placeholder |
| Beacons | Implemented | Overview table, detail panel, operations modal |
| Reports | Planned | Previously labeled Reporting |
| Assets | Planned | Owns Inventory as a sub-tab |
| Settings | Implemented | C2 URL configuration, connection status, C2 worker settings |
| Health | Implemented | Utility nav, protected readiness view |

### 2.2 Implemented Routes

| Route | Status |
|---|---:|
| `/login` | Implemented |
| `/home` | Implemented |
| `/projects` | Implemented |
| `/recon` | Basic |
| `/beacons` | Implemented |
| `/settings` | Implemented |
| `/settings/infrastructure` | Implemented |
| `/settings/c2` | Legacy redirect |
| `/health` | Implemented |

---

## 3. Target Primary Navigation

The side rail should contain 10 primary operator sections plus utility surfaces:

```text
+--------------------------------+
| Home       Dashboard overview |
| Projects   Engagement scope   |
| Recon      Discovery tools    |
| Beacons    Agents/sessions    |
| Exploits   Exploit planning   |
| Payloads   Payload builder    |
| Assets     Inventory/vulns    |
| Reports    Notes/exports      |
| Loot       Credentials/files  |
| Settings   Configuration      |
+--------------------------------+
| Realtime   Utility status     |
| Health     Utility readiness  |
+--------------------------------+
```

Important naming decisions:

- **Reports** replaces the earlier `Reporting` label.
- **Inventory** is not a primary side-tab. It lives under **Assets > Inventory**.
- **Loot** is a primary side-tab because credentials and collected artifacts are central operator workflows.
- **Findings** is not a primary side-tab. Vulnerabilities and finding-style records belong under **Assets** and **Reports** until a later feature changes that.

---

## 4. Target Secondary Navigation

Each primary section owns top-bar tabs. Root paths should render the first tab in each section.

| Section | Top tabs |
|---|---|
| Home | Overview, Activity Feed, Quick Actions |
| Projects | Projects, Scope, Timeline, Team |
| Recon | Tools, Runs, Results, Activity |
| Beacons | Overview, Sessions, Groups, Profiles, Deploy |
| Exploits | Browser, Suggestions, Execution, Results |
| Payloads | Generator, Encrypter, Obfuscator, Traffic Shaping, Output |
| Assets | Inventory, Hosts, Services, Vulnerabilities, Domains, Cloud Resources, Relationships |
| Reports | Notes, Campaign Reports, Host Reports, Vulnerability Reports, Exports |
| Loot | Credentials, Files, Secrets, Quick Save, Search |
| Settings | Connection, Infrastructure, Profiles, API Keys, Access, BFF, Plugins, Notifications |
| Health | Readiness, Liveness |

### 4.1 Route Map

```text
Home       /home, /home/activity, /home/actions
Projects   /projects, /projects/scope, /projects/timeline, /projects/team
Recon      /recon, /recon/runs, /recon/results, /recon/activity
Beacons    /beacons, /beacons/sessions, /beacons/groups, /beacons/profiles, /beacons/deploy
Exploits   /exploits, /exploits/suggestions, /exploits/execution, /exploits/results
Payloads   /payloads, /payloads/encrypter, /payloads/obfuscator, /payloads/traffic-shaping, /payloads/output
Assets     /assets, /assets/hosts, /assets/services, /assets/vulnerabilities, /assets/domains, /assets/cloud-resources, /assets/relationships
Reports    /reports, /reports/campaign, /reports/hosts, /reports/vulnerabilities, /reports/exports
Loot       /loot, /loot/files, /loot/secrets, /loot/quick-save, /loot/search
Settings   /settings, /settings/infrastructure, /settings/profiles, /settings/api-keys, /settings/access, /settings/bff, /settings/plugins, /settings/notifications
Health     /health, /health/live
```

Legacy route: `/settings/c2` redirects to `/settings/infrastructure`.

---

## 5. Section Specifications

### 5.1 Home

Purpose: At-a-glance operational overview.

Primary surfaces:

- Beacon and worker status summaries.
- Recent realtime activity feed.
- Quick actions for project creation, quick scan, and beacon deployment.
- Local BFF, C2, PostgreSQL, Redis, and realtime health indicators.

Stub requirements:

- Activity Feed can render recent-event placeholder rows.
- Quick Actions can open a planned quick-action modal.

### 5.2 Projects

Purpose: Engagement and scope management.

Primary surfaces:

- Project roster.
- Scope lists for domains and IP addresses.
- One active project selector.
- Timeline and team placeholders.

Stub requirements:

- Timeline tab shows locked chronology rows.
- Team tab shows planned collaborator/permission rows.

### 5.3 Recon

Purpose: Discovery tool orchestration.

Primary surfaces:

- Tool catalog grouped by Network, Web, DNS, Protocol, SSL/TLS, Cloud, and Enrichment.
- Runs table for active/completed scans.
- Results preview tied to Assets ingestion.
- Activity timeline.

Stub modal:

- Recon tool configuration.
- Fields planned for target input, execution target, rate limits, and output handling.

### 5.4 Beacons

Purpose: Manage active and historical beacons.

Primary surfaces:

- Overview table with sortable/filterable controlled-system rows.
- Sessions placeholder for shell, file browser, and Windows Registry Explorer interactions.
- Groups placeholder.
- C2 profiles placeholder.
- Deploy builder placeholder.

Stub modal:

- Beacon operations modal with command queue, interactive session, files/artifacts, credentials, and inventory actions.

### 5.5 Exploits

Purpose: Exploit selection, suggestions, execution planning, and results tracking with multi-source aggregation.

Primary surfaces:

- Exploit browser with catalog filters (source, CVE, affected service, platform, severity).
- Suggestions based on target profile (service enumeration results, asset metadata).
- Execution planner with payload binding and post-exploitation chaining.
- Results table with asset correlation and execution history.

Stub modal:

- Exploit details/configuration with CVE metadata, target selection, payload selection, and references.
- Exploit source attribution (Metasploit, ExploitDB, built-in, custom).

### 5.6 Payloads

Purpose: Multi-language payload generation, encryption, obfuscation, traffic shaping, and unified beacon deployment.

Primary surfaces:

- Generator with language selection (Go, Python, PowerShell, Bash, Rust, C#).
- Template browser (stager, reverse shell, bind shell, custom).
- Encrypter with algorithm selection.
- Obfuscator with encoder/transformer pipeline configuration.
- Traffic Shaping profile integration.
- Output with direct beacon deployment integration.

Stub modal:

- Payload builder with payload type, language, architecture, profile, and output options.
- Encoder chain configuration with preview.
- Beacon deployment wizard from generated payload.

### 5.7 Assets

Purpose: Centralized discovered inventory.

Primary surfaces:

- Inventory as the default tab.
- Hosts, services, vulnerabilities, domains, cloud resources, and relationships.
- Topology and relationship views in later features.

Stub panel:

- Asset detail side panel with metadata, relationships, linked beacons, scan history, vulnerabilities, notes, and quick actions.

### 5.8 Reports

Purpose: Notes, engagement reports, and exports.

Primary surfaces:

- Notes.
- Campaign reports.
- Host reports.
- Vulnerability reports.
- Exports.

Stub modal:

- Report builder with template, included data, export format, and scheduling placeholders.

### 5.9 Loot

Purpose: Credentials, files, secrets, and collected artifacts.

Primary surfaces:

- Credentials.
- Files.
- Secrets.
- Quick Save.
- Search.

Stub modal:

- Credential manual-entry modal with source, host, user, secret type, tags, and authorization note placeholders.

### 5.10 Settings

Purpose: Local and C2 configuration.

Primary surfaces:

- Connection.
- Infrastructure.
- Profiles.
- API Keys.
- Access.
- BFF.
- Plugins.
- Notifications.

Stub modals:

- Plugin manager.
- User management.

---

## 6. Modal and Panel Architecture

All modal surfaces must use a shared shell:

- `role="dialog"` and `aria-modal="true"`.
- Direct visible title and close control.
- Escape key closes.
- Centered modal for configuration flows.
- Side-panel variant for asset detail or inventory drilldown.
- Planned/locked content must be explicit.
- No backend write, task dispatch, or route mutation while the feature is stubbed.

Required shell modals:

| Modal | Trigger |
|---|---|
| Beacon operations | Double-click beacon row or operation action |
| Task execution | Beacon operations or bulk action stub |
| Recon tool configuration | Recon tool configure action |
| Exploit configuration | Exploit browser detail action |
| Payload builder | Payload generator action |
| Credential manual entry | Loot credentials action |
| Asset detail side panel | Asset row click |
| Asset merge | Assets management action |
| Report builder | Reports action |
| Plugin manager | Settings > Plugins |
| User management | Settings > Access (C2 admin; F0074/F0105) |

---

## 7. Stub Implementation Rules

This architecture document describes shell scaffolding, not feature completion.

Stub surfaces may:

- Add protected frontend routes.
- Render dense placeholder tables, toolbars, split panes, and empty states.
- Open modal shells with planned/locked content.
- Read existing local state such as C2 connection and active project.
- Display local sample rows clearly marked as planned or locked.

Stub surfaces must not:

- Add backend routes.
- Add database schema or migrations.
- Regenerate OpenAPI documents.
- Dispatch tasks, scans, exploits, payload generation, or credential operations.
- Mark future feature specs complete.

---

## 8. Feature Alignment

The shell refactor supports these planned features without completing them:

| Area | Feature ownership |
|---|---|
| Home dashboard | F0024 |
| Beacon management UI | F0025 |
| Task execution UI | F0026 |
| Realtime results UI | F0027 |
| Inventory/module browser | F0028 |
| Asset inventory and management | F0030-F0034 |
| Handler and scanner settings | F0038-F0049 |
| C2 operator auth and login UX | F0074 |
| Recon modules | F0050-F0073 |
| Reporting integration | F0072 |
| Exploit management system | F0080 |
| Payload generation system | F0081 |
| Post-exploitation orchestration | F0082 |
| Exploit source adapters | F0083 |
| Advanced post-exploitation | F0101-F0103 |

---

## 9. Open Questions

Resolved in this baseline:

- **Should Inventory and Assets be separate side tabs?** No. Inventory is under Assets.
- **Should Loot be top-level or part of Assets?** Top-level.
- **Should Exploits and Payloads be separate?** Yes.
- **Should there be a dedicated Post-Exploitation section?** No. Post-exploitation actions begin from Beacons, Inventory, and future module surfaces.
- **Should notes be global or project-scoped?** Project-scoped by default, with future copy/export behavior.

*End of document.*
