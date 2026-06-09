# F0106: Plugin Marketplace

## Metadata
| Field | Value |
|---|---|
| ID | F0106 |
| Priority | v2 |
| Status | Planned |
| MVP Phase | v2 |
| Depends on | F0041 |

## Summary
Community plugin marketplace for browsing, vetting, and installing third-party Xero plugins with signature verification, ratings, and version management.

## Requirements
- Marketplace catalog API with search, categories, and ratings
- Plugin packages signed by publisher; signature verified on install
- One-click install from marketplace to core plugin registry
- Publisher registration and plugin submission workflow
- Review status: pending, approved, rejected with reason

## Stages

### Stage 1: Catalog API
**Goal:** Marketplace backend with plugin metadata and search.
**Acceptance Criteria:**
- [ ] GET /api/v1/marketplace/plugins with search and category filter
- [ ] Plugin entry: name, author, description, version, rating, downloads
- [ ] Publisher ID and signature fingerprint in metadata

### Stage 2: Signature verification
**Goal:** Verify plugin package signature on install.
**Acceptance Criteria:**
- [ ] Ed25519 signature verification against publisher public key
- [ ] Unsigned or invalid signature rejected at install
- [ ] Signature check runs before plugin sandbox load

### Stage 3: Marketplace UI
**Goal:** Browse, search, and install plugins from UI.
**Acceptance Criteria:**
- [ ] Marketplace page with search and category filters
- [ ] Plugin detail shows README, version history, ratings
- [ ] Install button adds plugin to local registry

## Feature Acceptance Criteria

- [ ] Signed plugin installs successfully from marketplace
- [ ] Unsigned plugin rejected with clear signature error
- [ ] Installed marketplace plugin dispatchable as task module

## Test Plan

### Unit Tests
- [ ] test_marketplace_catalog_search
- [ ] test_signature_verify_valid
- [ ] test_signature_reject_unsigned
- [ ] test_install_adds_to_local_registry
- [ ] test_publisher_registration

### System / Integration Tests
- [ ] Browse marketplace; install signed plugin; appears in module list
- [ ] Reject unsigned plugin; error shown; registry unchanged
- [ ] Dispatch installed marketplace plugin; task completes

### Playwright Tests
- [ ] Marketplace page lists available plugins with ratings
- [ ] Plugin detail page shows README and install button
- [ ] Install plugin; success toast; plugin appears in module browser
