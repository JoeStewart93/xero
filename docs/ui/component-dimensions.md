# XERO UI Component Dimensions

**Version:** 2.0.0  
**Date:** June 13, 2026

Pixel tokens and layout grids for the XERO operator console. Applied via `styles.css` CSS variables and utility classes.

---

## Shell Chrome

| Element | Value |
|---------|------:|
| Brand stripe height | 3px |
| Side nav width | 104px |
| Side nav tab | 78 × 48px |
| Side nav tab font | 10.5px / 760 |
| Topbar min-height | 56px |
| Topbar padding | 8px 16px |
| Sub-nav tab height | 32px |
| Sub-nav tab min-width | 72px |
| Content max-width (default) | 1200px |
| Content max-width (wide) | 1680px |
| Content padding | 14px |

---

## Typography

| Role | Size | Weight | Line height |
|------|-----:|-------:|------------:|
| Page title (topbar, sr-only h1) | 15px | 760 | 20px |
| Section heading (in content) | 14px | 760 | 18px |
| Table header | 11px uppercase | 720 | 14px |
| Body | 13px | 400 | 18px |
| Muted | 12px | 400 | 16px |
| Modal title | 17px | 850 | 22px |
| Monospace IDs | 12px | 400 | 16px |

Font stack: Inter, ui-sans-serif, system-ui.  
Monospace: SFMono-Regular, Consolas, Liberation Mono, monospace.

---

## Controls

| Element | Value |
|---------|------:|
| Button min-height | 32px |
| Button padding | 0 12px |
| Button font | 12.5px / 760 |
| Button border-radius | 5px |
| Input height | 32px |
| Toolbar height | 40px |
| Shell action button min-width | 86px |

---

## Tables

| Element | Value |
|---------|------:|
| Header row height | 36px |
| Data row height | 38px |
| Cell padding | 8px 10px |

---

## Panels

| Element | Value |
|---------|------:|
| `workspace-panel` padding | 12px |
| Border radius | 6px |
| Border | 1px solid var(--xero-border) |
| Shadow (data workspaces) | 0 2px 8px rgba(0,0,0,0.1) |
| Grid gap (panels) | 12px |

Data workspaces use `.workspace-panel--flat` (no corner accents, reduced shadow).

---

## Page Grids

| Page | CSS class | Columns |
|------|-----------|---------|
| Beacons roster | `.beacons-roster-layout` | 100% table |
| Beacon workspace | `.beacon-workspace-body` | 220px + 1fr |
| Inventory | `.asset-inventory-workspace` | 240px + 1fr + 380px |
| Recon Launch | `.recon-workspace` | 200px + 0.8fr + 1.2fr |
| Modules | `.module-inventory-workspace` | 1.4fr + 0.86fr |
| Projects | `.projects-workspace-grid--modal-refactor` | 0.95fr + 0.75fr |
| Settings | `.settings-layout` | 200px + 1fr |
| Home | `.dashboard-overview-grid` | 320px + 1fr |
| Task execution | `.task-execution-layout` | 280px + 320px + 1fr |

---

## Modals

| Variant | Width | Class |
|---------|------:|-------|
| center | min(760px, 100vw − 48px) | `.modal-shell--center` |
| wide | min(1180px, 100vw − 48px) | `.modal-shell--wide` |
| side | min(520px, 100vw − 48px) | `.modal-shell--side` |

Backdrop: z-index 80, blur, dark overlay.

---

## Design Tokens (`:root`)

| Token | Value |
|-------|-------|
| `--xero-bg` | `#030609` |
| `--xero-surface` | `rgba(7,12,18,0.94)` |
| `--xero-border` | `rgba(0,231,255,0.24)` |
| `--xero-text` | `#f4f7fb` |
| `--xero-muted` | `#9aadc0` |
| `--xero-primary` | `#00e7ff` |
| `--xero-danger` | `#ff3045` |

---

## Spacing Scale

4 / 8 / 12 / 14 / 16 / 24 / 32px
