# F0036: LDAP Enumeration

## Metadata
| Field | Value |
|---|---|
| ID | F0036 |
| Priority | P1 |
| Status | Planned |
| MVP Phase | 4 |
| Depends on | F0016 |

## Summary
Built-in LDAP enumeration module for querying Active Directory users, groups, computers, and domain policy from domain-joined or network-reachable lab domain controllers. It uses the scanner execution model: embedded C2 scanner by default, external scanner selection when available, and later beacon pivot execution for internal vantage points.

## Requirements
- builtin.ldapenum module with dc_host, bind_dn, password, base_dn args
- Queries: users, groups, computers, domain admins, GPOs
- Paged LDAP results for large directories
- LDAPS (636) and STARTTLS (389) supported
- Results enrich asset inventory with AD metadata
- Execution target defaults to embedded C2 scanner unless an external scanner or later pivot route is selected

## Stages

### Stage 1: LDAP module schema
**Goal:** Define ldapenum args and query type selection.
**Acceptance Criteria:**
- [ ] Args: dc_host, port, bind_dn, password, base_dn, query_types[]
- [ ] Query types: users, groups, computers, domain_admins
- [ ] Max results limit default 1000 with pagination

### Stage 2: Scanner LDAP client
**Goal:** Scanner execution performs LDAP queries with paging.
**Acceptance Criteria:**
- [ ] LDAP bind with provided credentials
- [ ] Paged search for large result sets
- [ ] STARTTLS upgrade on port 389 when configured

### Stage 3: AD result display
**Goal:** UI tables for users, groups, and computers.
**Acceptance Criteria:**
- [ ] Users table: cn, sAMAccountName, memberOf, lastLogon
- [ ] Groups table: cn, members count, groupType
- [ ] Export results as CSV

## Feature Acceptance Criteria

- [ ] LDAP user enumeration returns accurate count against lab AD
- [ ] Domain admins query identifies DA group members
- [ ] LDAPS connection succeeds against lab DC on port 636

## Test Plan

### Unit Tests
- [ ] test_ldapenum_args_validation
- [ ] test_ldap_paged_search_mock
- [ ] test_starttls_upgrade
- [ ] test_bind_failure_error
- [ ] test_result_user_schema

### System / Integration Tests
- [ ] Run ldapenum against lab DC; user count matches ldapsearch
- [ ] Domain admin query returns expected members
- [ ] LDAP results update asset domain metadata

### Playwright Tests
- [ ] LDAP enum module in module browser with query type checkboxes
- [ ] Submit ldapenum; users table renders in result panel
- [ ] Export CSV button downloads LDAP results
