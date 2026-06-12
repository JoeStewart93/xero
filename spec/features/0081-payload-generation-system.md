# F0081: Payload Generation System

## Metadata
| Field | Value |
|---|---|
| ID | F0081 |
| Priority | P0 |
| Status | Planned |
| MVP Phase | 5 |
| Depends on | F0015, F0021, F0015.01-AMD |

## Summary
Multi-language payload generation system supporting Go, Python, PowerShell, Bash, Rust, and C#. Provides template-based payload configuration, encoder/obfuscator pipeline, traffic shaping profile integration, and unified beacon deployment workflow.

## Requirements
- Multi-language payload generators (Go, Python, PowerShell, Bash, Rust, C#)
- Template-based payload configuration (stager, reverse shell, bind shell, custom)
- Encoder/obfuscator pipeline with configurable transformations
- Traffic shaping profile integration from F0021
- Unified beacon deployment integration
- Payload caching for performance
- Generated binary, script, shellcode, and packaged payload outputs are stored through F0015.01-AMD artifact storage.

## Stages

### Stage 1: Payload generator core
**Goal:** Implement core payload generation for all supported languages.
**Acceptance Criteria:**
- [ ] Payload templates: stager, reverse_shell, bind_shell for each language
- [ ] Generator API: POST /api/v1/payloads/generate with language, template, options
- [ ] Output formats: binary, script, shellcode
- [ ] payloads table with generation metadata
- [ ] Template validation and option schema

### Stage 2: Encoder/obfuscator pipeline
**Goal:** Implement encoder chain with configurable transformations.
**Acceptance Criteria:**
- [ ] Built-in encoders: XOR, Base64, custom
- [ ] Encoder chain configuration: order, options per encoder
- [ ] encoder_configs table for saved configurations
- [ ] Encoder API: POST /api/v1/payloads/encode with payload_id, encoder_chain
- [ ] Preview mode showing encoded output sample
- [ ] Decoder for verification

### Stage 3: Traffic shaping integration
**Goal:** Integrate traffic shaping profiles into payload generation.
**Acceptance Criteria:**
- [ ] Traffic shaping profile selection in payload options
- [ ] Profile parameters embedded in generated payload
- [ ] Validation of profile compatibility with payload type
- [ ] Profile preview showing expected behavior

### Stage 4: Beacon deployment integration
**Goal:** Enable direct beacon deployment from generated payloads.
**Acceptance Criteria:**
- [ ] Deploy API: POST /api/v1/payloads/{id}/deploy with beacon options
- [ ] Integration with F0015 beacon registration
- [ ] Deployment status tracking
- [ ] Link payload to deployed beacon
- [ ] Rollback on deployment failure

### Stage 5: Caching and optimization
**Goal:** Cache generated payloads for performance.
**Acceptance Criteria:**
- [ ] Redis cache for generated payloads by hash
- [ ] Cache invalidation on template/option changes
- [ ] Cache hit/miss metrics
- [ ] Configurable cache TTL

## Feature Acceptance Criteria

- [ ] Generate valid payloads in all six languages (Go, Python, PowerShell, Bash, Rust, C#)
- [ ] Encoder pipeline applies transformations correctly
- [ ] Traffic shaping profiles integrate with payload generation
- [ ] Generated payloads can be deployed as beacons
- [ ] Payload cache improves generation performance

## Test Plan

### Unit Tests
- [ ] test_payload_generator_go
- [ ] test_payload_generator_python
- [ ] test_payload_generator_powershell
- [ ] test_payload_generator_bash
- [ ] test_payload_generator_rust
- [ ] test_payload_generator_csharp
- [ ] test_encoder_xor
- [ ] test_encoder_base64
- [ ] test_encoder_chain
- [ ] test_traffic_shaping_integration
- [ ] test_beacon_deployment_workflow

### System / Integration Tests
- [ ] Generate Go reverse shell; validates and executes
- [ ] Generate PowerShell stager; encodes with XOR; executes
- [ ] Apply traffic shaping profile; payload respects settings
- [ ] Deploy generated payload as beacon; registration succeeds
- [ ] Cache hit on repeated generation with same options

### Playwright Tests
- [ ] Payload generator UI shows all language options
- [ ] Select template and configure options
- [ ] Configure encoder chain with preview
- [ ] Deploy payload as beacon from output
- [ ] Generated payload appears in payload history
