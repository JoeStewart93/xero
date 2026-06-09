# F0041: Plugin API

## Metadata
| Field | Value |
|---|---|
| ID | F0041 |
| Priority | P1 |
| Status | Planned |
| MVP Phase | 5 |
| Depends on | F0016, F0004 |

## Summary
Language-agnostic plugin contract and Xero C2 plugin manager that loads, registers, and dispatches third-party modules alongside built-in scanning and enumeration modules.

## Requirements
- Multi-language plugin API with language-agnostic contract
- Plugin manifest: name, version, author, args_schema, entry_point
- Plugin registration via POST /api/v1/plugins
- Plugin sandbox: timeout, memory limit, no direct DB access
- Plugin modules appear in module registry alongside builtins

## Stages

### Stage 1: Plugin contract
**Goal:** Define manifest schema and execution interface.
**Acceptance Criteria:**
- [ ] Manifest JSON schema validated on registration
- [ ] Contract defines execute(ctx, args) -> result interface
- [ ] Version compatibility check with C2 API version

### Stage 2: Plugin manager
**Goal:** Backend loads and manages plugin lifecycle.
**Acceptance Criteria:**
- [ ] plugins table stores manifest, path, status, enabled flag
- [ ] Dispatch routes task to plugin entry point
- [ ] Plugin crash isolated; C2 remains stable

### Stage 3: Registration API
**Goal:** Operator uploads and enables plugins.
**Acceptance Criteria:**
- [ ] POST /plugins accepts manifest + artifact upload
- [ ] Enable/disable toggle without uninstall
- [ ] Plugin list shows status and last error

## Feature Acceptance Criteria

- [ ] Registered plugin module dispatchable as task to beacon
- [ ] Plugin crash returns error result without C2 restart
- [ ] Plugin manifest validation rejects malformed registrations

## Test Plan

### Unit Tests
- [ ] test_plugin_manifest_validation
- [ ] test_plugin_register_and_enable
- [ ] test_plugin_dispatch_calls_entry_point
- [ ] test_plugin_crash_isolated
- [ ] test_plugin_disable_prevents_dispatch

### System / Integration Tests
- [ ] Register test plugin; appears in /modules list
- [ ] Dispatch plugin task; result returned correctly
- [ ] Disable plugin; dispatch returns module unavailable error

### Playwright Tests
- [ ] Plugins settings page lists registered plugins
- [ ] Upload plugin manifest; plugin appears in module browser
- [ ] Disable plugin; module grayed out in module browser
