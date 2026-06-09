# F0037: DNS Enumeration

## Metadata
| Field | Value |
|---|---|
| ID | F0037 |
| Priority | P1 |
| Status | Planned |
| MVP Phase | 4 |
| Depends on | F0016 |

## Summary
Built-in DNS enumeration module for zone transfers, subdomain brute-force, reverse lookups, and SRV record discovery against authorized lab DNS infrastructure. It uses the scanner execution model: embedded C2 scanner by default, external scanner selection when available, distributed scanner pools for large workloads, and later beacon pivot execution for internal DNS vantage points.

## Requirements
- builtin.dnsenum module with domain, dns_server, enum_types args
- Enum types: zone_transfer, subdomain_brute, reverse_ptr, srv_records
- Subdomain wordlist bundled with configurable size
- Results create discovered_host assets for found subdomains
- Rate limited queries to avoid DNS flooding
- Execution target defaults to embedded C2 scanner unless an external scanner, distributed pool, or later pivot route is selected

## Stages

### Stage 1: DNS module schema
**Goal:** Register dnsenum with enum type and target args.
**Acceptance Criteria:**
- [ ] Args: domain, dns_server, enum_types[], brute_wordlist_size
- [ ] Zone transfer attempts AXFR against specified NS
- [ ] Brute force uses bundled wordlist (small/medium/large)

### Stage 2: Scanner DNS resolver
**Goal:** Scanner execution performs DNS queries with rate limiting.
**Acceptance Criteria:**
- [ ] AXFR zone transfer with result parsing
- [ ] Subdomain brute with concurrent but rate-limited lookups
- [ ] SRV record query for AD service discovery

### Stage 3: DNS result display
**Goal:** UI shows records by type with asset links.
**Acceptance Criteria:**
- [ ] Subdomains listed with resolved IP if A record found
- [ ] SRV records show service targets and ports
- [ ] Create asset button for discovered subdomains

## Feature Acceptance Criteria

- [ ] Subdomain brute discovers lab hidden subdomain from wordlist
- [ ] SRV records reveal lab AD service endpoints
- [ ] DNS query rate stays under 50 qps to configured server

## Test Plan

### Unit Tests
- [ ] test_dnsenum_args_validation
- [ ] test_axfr_parse_mock
- [ ] test_subdomain_brute_finds_match
- [ ] test_dns_rate_limiter
- [ ] test_srv_record_parse

### System / Integration Tests
- [ ] Run dnsenum brute against lab DNS; finds known subdomain
- [ ] SRV query returns _ldap._tcp records for lab AD
- [ ] Discovered subdomains appear as assets in inventory

### Playwright Tests
- [ ] DNS enum module shows enum type selection in task form
- [ ] Subdomain brute results list found hosts with IPs
- [ ] Create asset from DNS result adds to inventory
