# F0042: Python Plugin Reference

## Metadata
| Field | Value |
|---|---|
| ID | F0042 |
| Priority | P1 |
| Status | Planned |
| MVP Phase | 5 |
| Depends on | F0041 |

## Summary
Reference Python plugin implementation demonstrating the plugin contract, packaged with example modules and documentation for rapid P1 operator extension development.

## Requirements
- Python reference plugin under `platform/services/c2-api/xero_c2/plugins/python/`
- Example plugin: hello_world and env_info modules
- Plugin SDK package with typed args and result helpers
- README with authorized-use disclaimer and dev guide
- pytest suite for reference plugin execute paths

## Stages

### Stage 1: Python SDK
**Goal:** Create xero_plugin SDK package with base class.
**Acceptance Criteria:**
- [ ] XeroPlugin base class with execute() abstract method
- [ ] Args validation via Pydantic models
- [ ] Result helper formats JSON output consistently

### Stage 2: Reference plugins
**Goal:** Ship hello_world and env_info examples.
**Acceptance Criteria:**
- [ ] hello_world returns greeting with beacon hostname
- [ ] env_info returns OS env vars (sanitized, no secrets)
- [ ] Both plugins register via standard manifest

### Stage 3: Documentation
**Goal:** Plugin development guide with examples.
**Acceptance Criteria:**
- [ ] docs/plugins/python.md with step-by-step tutorial
- [ ] Manifest template and test instructions
- [ ] Authorized lab use warning prominent in guide

## Feature Acceptance Criteria

- [ ] hello_world Python plugin dispatchable and returns expected greeting
- [ ] Third-party developer can create new plugin in under 30 minutes using guide
- [ ] Reference plugin pytest suite passes in CI

## Test Plan

### Unit Tests
- [ ] test_hello_world_plugin_execute
- [ ] test_env_info_plugin_sanitized_output
- [ ] test_plugin_sdk_args_validation
- [ ] test_manifest_generation_helper

### System / Integration Tests
- [ ] Register hello_world plugin; dispatch to beacon; result received
- [ ] Invalid plugin args return validation error before dispatch
- [ ] Reference plugins included in CI test suite

### Playwright Tests
- [ ] hello_world plugin visible in module browser after registration
- [ ] Dispatch hello_world; result shows greeting in result panel
- [ ] Plugin docs link accessible from settings
