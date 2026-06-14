# XERO UI Navigation Specification

**Version:** 2.0.0  
**Date:** June 13, 2026  
**Status:** Active — post-restructure baseline

This document defines routes, tabs, modals, buttons, and cross-entity links for the XERO operator console.

---

## Primary Sidebar

| Order | Section | Route | Requires C2 | Sub-tabs shown |
|------:|---------|-------|:-----------:|:--------------|
| 1 | Home | `/home` | No | Overview only |
| 2 | Projects | `/projects` | Yes | Projects, Scope |
| 3 | Recon | `/recon` | Yes | Launch only |
| 4 | Beacons | `/beacons` | Yes | Roster, Sessions, Deploy |
| 5 | Exploits | `/exploits` | Yes | None (planned empty state) |
| 6 | Payloads | `/payloads/traffic-patterns` | Yes | Traffic Patterns only |
| 7 | Modules | `/modules` | Yes | Catalog only |
| 8 | Assets | `/assets` | Yes | Inventory only |
| 9 | Reports | `/reports` | Yes | None (planned empty state) |
| 10 | Loot | `/loot` | Yes | None (planned empty state) |
| 11 | Settings | `/settings` | No | Left sub-nav (see below) |
| — | Health | `/health` | No | Readiness only (utility nav) |

Tabs with `enabled: false` in `navigation.ts` are hidden from the top sub-nav.

---

## Section Specifications

### Home

| Tab | Route | Container | Buttons |
|-----|-------|-----------|---------|
| Overview | `/home` | Page, 2-col grid | — |

**Layout:** 320px status column + fluid activity list. Inline KPI strip (no nested cards).

**Links:** Recent tasks → `/beacons/:id/commands?task_id=T`

---

### Projects

| Tab | Route | Container | Buttons |
|-----|-------|-----------|---------|
| Projects | `/projects` | Page, 2-col roster | Create, Manage, Delete |
| Scope | `/projects/:projectId/scope` | Page, targets table | Add target, Remove target |

**Modals:**
- Create project — `?create=1`, center 760px
- Delete confirm — center 520px

**Manage project:** `/projects/:projectId` page (rename, activate, delete).

**Create → Target:** `/projects/:activeProjectId/scope` or `/projects?create=1` if no active project.

---

### Recon

| Tab | Route | Container | Buttons |
|-----|-------|-----------|---------|
| Launch | `/recon` | Page, 3-col tri-pane | Run scan, Cancel job |

**Layout:** 200px scanners | 0.8fr jobs | 1.2fr output (dominant).

**Modals:** None — NMAP config is inline in left column.

**Links:** Job result host → `/assets?asset_id=A`

---

### Beacons

| Tab | Route | Container | Buttons |
|-----|-------|-----------|---------|
| Roster | `/beacons` | Page, full-width table | Search, Filter, Export CSV |
| Sessions | `/beacons/sessions` | Page, session list | Open beacon |
| Deploy | `/beacons/deploy` | Page, builder form | Request build, Download |

#### Beacon workspace (routed, replaces modal)

| Route | Content | Buttons |
|-------|---------|---------|
| `/beacons/:beaconId` | Redirect → commands | — |
| `/beacons/:beaconId/commands` | TaskExecutionPanel | Queue task, Cancel |
| `/beacons/:beaconId/session` | Shell (xterm) | Connect, Disconnect |
| `/beacons/:beaconId/files` | File browser | Upload, Download |
| `/beacons/:beaconId/registry` | Registry explorer | — |
| `/beacons/:beaconId/controls` | Profile assign, kill | Assign profile, Kill |

**Layout:** 220px operation rail + fluid content pane.

**Modals:** Kill beacon confirm only (520px center).

**Roster interaction:** Row click / Enter → `/beacons/:id/commands`. No detail sidebar.

**Query migration:** `/beacons?module=M&beacon_id=X` → `/beacons/X/commands?module=M`

---

### Payloads

| Tab | Route | Container | Buttons |
|-----|-------|-----------|---------|
| Traffic Patterns | `/payloads/traffic-patterns` | Page + table | New profile, Edit, Delete |

**Modals:** Traffic profile editor (760px center).

---

### Modules

| Tab | Route | Container | Buttons |
|-----|-------|-----------|---------|
| Catalog | `/modules` | Page, 2-col table + detail | Run module |

**Layout:** 1.4fr catalog table + 0.86fr detail pane.

**Links:** Run → `/beacons/:id/commands?module=M` or `/recon?module=M`

---

### Assets

| Tab | Route | Container | Buttons |
|-----|-------|-----------|---------|
| Inventory | `/assets` | Page, 3-pane | Refresh, Group filter |

**Layout:** 240px groups | fluid list | 380px detail.

**Links:**
- Linked beacon → `/beacons/:id/commands`
- Edit grouping rules → `/settings/grouping`

**Modals:** None for detail (inline pane). Future: asset merge confirm.

---

### Exploits / Reports / Loot

Single planned empty state per section. No sub-tabs. No stub tables.

---

### Settings

Top sub-nav removed. In-content left rail (200px):

| Item | Route | Status |
|------|-------|--------|
| Connection | `/settings` | Live |
| Infrastructure | `/settings/infrastructure` | Live |
| Grouping | `/settings/grouping` | Live |
| API Keys | `/settings/api-keys` | Planned empty state |

**Modals:** Worker pair/launch/stop (760px center).

**C2 status button:** `/settings/infrastructure` when connected; `/settings` when disconnected.

---

### Health

| Tab | Route | Status |
|-----|-------|--------|
| Readiness | `/health` | Live |

---

## Modal Registry

| Modal | Trigger | Variant | Max width |
|-------|---------|---------|-----------|
| Create project | New → Project | center | 760px |
| Delete project | Manage → Delete | center | 520px |
| Kill beacon | Controls → Kill | center | 520px |
| Traffic profile editor | Traffic Patterns → Edit | center | 760px |
| Worker pair/launch | Infrastructure | center | 760px |

Removed: Beacon operations modal, Recon scan config modal, StubSectionPage demo modals.

---

## Cross-Entity Navigation

| From | To | Pattern |
|------|-----|---------|
| Inventory detail → beacon | `/beacons/:id/commands` | Link |
| Home task row | `/beacons/:id/commands?task_id=T` | Link |
| Recon result | `/assets?asset_id=A` | query select |
| Module Run | workspace or recon route | module kind |
| Inventory groups | `/settings/grouping` | text link |
| Task completion toast | `/beacons/:id/commands?task_id=T` | navigate |

---

## Entity UI Rules

| Relationship | Rule |
|---|---|
| Project → Targets | 1:N; scope selector filters when enforced |
| Beacon → Task | 1:N; tasks scoped to one beacon |
| Task → TaskResult | 1:1 per row |
| Beacon → TrafficProfile | 0..1 assignment |
| Asset ↔ Beacon | 0..1 link display |
| ScanJob → Assets | result links to asset |
