# XERO UI Restructure — Rationale & Self-Review

**Version:** 2.0.0  
**Date:** June 13, 2026

---

## Goals

1. Stop navigation from promising features that exist only as stubs or hidden modals.
2. Route persistent operator work (beacon tasking, sessions) instead of trapping it in modals.
3. Increase information density by flattening card nesting and tightening chrome.
4. Wire cross-entity links so operators can traverse beacon ↔ asset ↔ task naturally.

---

## Key Decisions

### Routed beacon workspace (replaces modal)

**Why:** Terminal, file browser, and task queue need full viewport height, shareable URLs, and browser back/forward.

**Risk:** Large refactor of `BeaconsPage.tsx`.

**Mitigation:** Phased extraction to `BeaconWorkspacePage`; query param compatibility during transition.

### Hide unimplemented sub-tabs

**Why:** ~40 stub routes with fake tables made the product feel broken.

**Risk:** Less roadmap visibility in nav.

**Mitigation:** Primary sidebar items remain; section home shows honest "planned" empty state.

### Modules promoted to primary nav

**Why:** `/modules` under Assets tabs broke active-state highlighting and misclassified catalog as inventory facet.

**Risk:** +1 sidebar item.

**Mitigation:** Insert between Payloads and Assets — matches operator workflow (configure modules → run on beacons).

### Settings left sub-nav

**Why:** 8 horizontal tabs overflow and don't scale.

**Risk:** Layout change for one section only.

**Mitigation:** Stripe-style 200px rail; top sub-nav hidden for Settings.

### Inline recon scan form

**Why:** Modal disconnected scan config from live job list.

**Risk:** Narrower scanner column (200px).

**Mitigation:** Scanner list becomes compact table, not cards.

---

## What We Did NOT Change

| Item | Reason |
|------|--------|
| 104px icon sidebar | Works for 11 sections; widening is scope creep |
| Primary nav order | Matches operator workflow and existing spec |
| Loot/Reports/Exploits as primary items | Roadmap signaling |
| Traffic profile editor as modal | Finite CRUD — correct container |
| Inventory 3-pane layout | Correct master-detail pattern |
| Login standalone | No shell needed |
| Beacons Deploy as full page | Multi-step builder needs space |
| XERO cyan/red brand tokens | Product identity — reduced application, not palette |
| `workspace-panel` on Settings/empty states | Appropriate chrome for config surfaces |

---

## Justification Matrix

| Decision | Benefit | Accepted tradeoff |
|----------|---------|-------------------|
| Route beacon ops | URLs, back button, terminal height | Refactor cost |
| Hide stub tabs | Honest UX | Fewer nav previews |
| Remove Assets facet tabs | No empty routes | Filters come later on Inventory |
| Settings left nav | Scales beyond 4 items | One-section layout change |
| Flatten Home KPIs | Faster scan | Less visual separation |
| 3-col TaskExecutionPanel | Stream output dominant | Wider minimum viewport |

---

## Alignment with Prior Spec

[`spec/architecture/ui-architecture.md`](../architecture/ui-architecture.md) v1.1.0 described beacon operations as a stub modal. v2.0 updates that to routed workspace and documents hidden-tab strategy. Stub rules (§7) remain: planned features must not fake data or dispatch backend operations.

---

## Related Documents

- [Navigation spec](./navigation-spec.md)
- [Component dimensions](./component-dimensions.md)
