# F0055: NetBIOS Enumeration

## Metadata
| Field | Value |
|---|---|
| ID | F0055 |
| Priority | P0 |
| Status | Planned |
| MVP Phase | 3 |
| Depends on | F0035, F0069 |

## Summary
NetBIOS name service enumeration for Windows network discovery. Extracts hostnames, user accounts, domain/workgroup information, and MAC addresses from NetBIOS name tables. Works alongside SMB enumeration (F0035).

## Requirements
- NetBIOS name queries (NS lookup)
- User enumeration via NetBIOS
- Domain/workgroup discovery
- MAC address extraction
- Integration with SMB enum (F0035)
- Support for both scanner service and beacon execution

## Module Arguments

`python
{
    \"targets\": [\"192.168.1.100\", \"192.168.1.0/24\"],
    \"enum_types\": [\"names\", \"users\", \"sessions\", \"domain_info\"],
    \"timeout_ms\": 5000,
    \"execution_target\": \"auto\"
}
`

## NetBIOS Name Types

| Type | Code | Description |
| :--- | :--- | :--- |
| Workstation Service | 0x00 | Machine name |
| Server Service | 0x20 | Server name |
| Messenger Service | 0x1E | Workgroup/Domain name |
| Browser Service | 0x1B | Master browser |
| Domain Controller | 0x1B | DC name |

## Result Schema

`json
{
    \"target\": \"192.168.1.100\",
    \"query_time\": \"2024-01-15T10:30:00Z\",
    \"netbios_names\": [
        {
            \"name\": \"WORKSTATION\",
            \"type\": \"0x00\",
            \"type_description\": \"Workstation Service\",
            \"status\": \"registered\",
            \"unique\": true
        },
        {
            \"name\": \"WORKSTATION\",
            \"type\": \"0x20\",
            \"type_description\": \"Server Service\",
            \"status\": \"registered\",
            \"unique\": true
        },
        {
            \"name\": \"WORKGROUP\",
            \"type\": \"0x1E\",
            \"type_description\": \"Messenger Service\",
            \"status\": \"registered\",
            \"unique\": false
        },
        {
            \"name\": \"WORKGROUP\",
            \"type\": \"0x1B\",
            \"type_description\": \"Browser Service\",
            \"status\": \"registered\",
            \"unique\": false
        }
    ],
    \"hostname\": \"WORKSTATION\",
    \"domain\": \"WORKGROUP\",  // or \"CORP.LOCAL\" if domain-joined
    \"workgroup\": \"WORKGROUP\",
    \"mac_address\": \"AA:BB:CC:DD:EE:FF\",
    \"dns_hostname\": \"workstation.corp.local\",
    \"users\": [
        \"Administrator\",
        \"jsmith\",
        \"guest\",
        \"DefaultAccount\"
    ],
    \"sessions\": [
        {
            \"user\": \"jsmith\",
            \"connected_time\": \"2024-01-15T09:00:00Z\",
            \"idle_time\": 3600
        }
    ],
    \"is_domain_controller\": false,
    \"is_master_browser\": true,
    \"summary\": {
        \"total_names\": 4,
        \"total_users\": 4,
        \"total_sessions\": 1
    }
}
`

## Stages

### Stage 1: NetBIOS Module Backend
**Goal:** Register netbios module with schema.
**Acceptance Criteria:**
- [ ] Module registered as uiltin.recon.netbios
- [ ] Args validation for targets, enum_types
- [ ] impacket library integration
- [ ] Module metadata exposed in /api/v1/modules

### Stage 2: NetBIOS Name Queries
**Goal:** Query NetBIOS name tables.
**Acceptance Criteria:**
- [ ] NetBIOS NS lookup via impacket
- [ ] Name type decoding
- [ ] Status interpretation (registered, conflicted, etc.)
- [ ] Timeout handling

### Stage 3: User & Session Enumeration
**Goal:** Extract user and session information.
**Acceptance Criteria:**
- [ ] User enumeration via NetBIOS
- [ ] Session listing
- [ ] Domain info extraction
- [ ] MAC address retrieval

### Stage 4: Integration
**Goal:** Link with SMB enumeration results.
**Acceptance Criteria:**
- [ ] Results combined with SMB enum (F0035)
- [ ] Host assets enriched
- [ ] User accounts added to inventory

## Feature Acceptance Criteria

- [ ] NetBIOS name queries return hostnames
- [ ] User enumeration via NetBIOS works
- [ ] Domain/workgroup correctly identified
- [ ] MAC addresses extracted
- [ ] Results integrate with SMB enum
- [ ] Works from beacon on target network

## Test Plan

### Unit Tests
- [ ] test_netbios_args_validation
- [ ] test_name_type_decoding
- [ ] test_status_interpretation
- [ ] test_mac_address_parsing

### System / Integration Tests
- [ ] NetBIOS query against Windows host succeeds
- [ ] User enumeration returns accounts
- [ ] Domain name extracted for domain-joined host
- [ ] Workgroup name extracted for workgroup host
- [ ] MAC address retrieved
- [ ] Timeout handled for unresponsive hosts

### Playwright Tests
- [ ] NetBIOS module visible in Recon module browser
- [ ] Submit NetBIOS task with valid target
- [ ] Results show hostname and domain
- [ ] Users listed in results
- [ ] Session information displayed

## NetBIOS Implementation

`python
from impacket.netbios import NetBIOSTCPIP, NetBIOS_NAME_TYPE_UNIQUE
from impacket.uuid import bin_to_string

def query_netbios_names(ip: str, timeout: int = 5000) -> dict:
    \"\"\"Query NetBIOS names for a target.\"\"\"
    results = {
        \"target\": ip,
        \"netbios_names\": [],
        \"hostname\": None,
        \"domain\": None,
        \"workgroup\": None,
        \"mac_address\": None,
    }

    try:
        # Create NetBIOS session
        nb = NetBIOSTCPIP(ip)
        nb.setTimeout(timeout / 1000.0)
        nb.connect()

        # Query name table (0x00-0x1F)
        for name_type in range(0x00, 0x20):
            try:
                response = nb.query_name_table(name_type)
                if response:
                    name_info = parse_name_response(response, name_type)
                    if name_info:
                        results[\"netbios_names\"].append(name_info)

                        # Extract hostname and domain
                        if name_type == 0x00 and name_info[\"status\"] == \"registered\":
                            results[\"hostname\"] = name_info[\"name\"]
                        elif name_type == 0x1E and name_info[\"status\"] == \"registered\":
                            results[\"domain\"] = name_info[\"name\"]
                            results[\"workgroup\"] = name_info[\"name\"]

            except Exception:
                continue

        nb.close()

    except Exception as e:
        results[\"error\"] = str(e)

    return results

def parse_name_response(response: bytes, name_type: int) -> dict:
    \"\"\"Parse NetBIOS name response.\"\"\"
    name_types = {
        0x00: \"Workstation Service\",
        0x03: \"Messenger Service\",
        0x06: \"RAS Server Service\",
        0x1F: \"NetDDE Service\",
        0x10: \"Network Monitor Agent\",
        0x11: \"Computer Browser\",
        0x12: \"Master Browser\",
        0x1B: \"Domain Master Browser\",
        0x1C: \"Domain Controller\",
        0x1E: \"Domain Name\",
        0x20: \"Server Service\",
    }

    return {
        \"name\": response.get(\"name\"),
        \"type\": f\"0x{name_type:02X}\",
        \"type_description\": name_types.get(name_type, \"Unknown\"),
        \"status\": response.get(\"status\", \"unknown\"),
        \"unique\": name_type < 0x20,
    }

def enumerate_netbios_users(ip: str, timeout: int = 5000) -> list[str]:
    \"\"\"Enumerate users via NetBIOS.\"\"\"
    users = []

    try:
        from impacket.smbconnection import SMBConnection

        # Try null session
        smb = SMBConnection(ip, ip)
        smb.login('', '')

        # Enumerate users via SAMR
        from impacket.dcerpc.v5 import samr, rpcrt

        rpc = smb.get_dce_rpc(samr.MSRPC_UUID_SAMR)
        rpc.connect()
        rpc.bind(samr.MSRPC_UUID_SAMR)

        # Connect to local SAM database
        samr_hDomain = samr.hSamrConnect(rpc)[\"ServerHandle\"]
        samr_hDomain = samr.hSamrOpenDomain(rpc, samr_hDomain,
                                             samr.MAXIMUM_ALLOWED,
                                             samr.DOMAIN_USER_ENUMERATION_ACCESS)[\"DomainHandle\"]

        # Enumerate users
        while True:
            try:
                resp = samr.hSamrEnumerateUsersInDomain(rpc, samr_hDomain,
                                                         samr.USER_NORMAL_ACCOUNT,
                                                         samr.MAXIMUM_ALLOWED, 0)
                users.extend([u['name'] for u in resp['Buffer']['Buffer']))
                if not resp['ResumeHandle']:
                    break
            except samr.DCERPCSessionError:
                break

        rpc.disconnect()
        smb.logoff()

    except Exception:
        pass  # Null session may not be available

    return users
`

## Name Type Reference

`python
NETBIOS_NAME_TYPES = {
    0x00: {\"name\": \"Workstation Service\", \"unique\": True, \"desc\": \"Machine name\"},
    0x01: {\"name\": \"Messenger Service\", \"unique\": False, \"desc\": \"NetDDE\"},
    0x03: {\"name\": \"Messenger Service\", \"unique\": True, \"desc\": \"File & Print\"},
    0x06: {\"name\": \"RAS Server Service\", \"unique\": True, \"desc\": \"Remote Access\"},
    0x1F: {\"name\": \"NetDDE Service\", \"unique\": True, \"desc\": \"NetDDE\"},
    0x10: {\"name\": \"Network Monitor Agent\", \"unique\": True, \"desc\": \"Monitor\"},
    0x11: {\"name\": \"Computer Browser\", \"unique\": False, \"desc\": \"Browser election\"},
    0x12: {\"name\": \"Master Browser\", \"unique\": False, \"desc\": \"Master browser\"},
    0x1B: {\"name\": \"Domain Master Browser\", \"unique\": False, \"desc\": \"DC or PDC\"},
    0x1C: {\"name\": \"Domain Controllers\", \"unique\": False, \"desc\": \"DC list\"},
    0x1E: {\"name\": \"Domain Name\", \"unique\": False, \"desc\": \"Workgroup/Domain\"},
    0x1F: {\"name\": \"NetDDE\", \"unique\": False, \"desc\": \"NetDDE\"},
    0x20: {\"name\": \"Server Service\", \"unique\": True, \"desc\": \"SMB server\"},
    0x21: {\"name\": \"MESSENGER\", \"unique\": True, \"desc\": \"Messenger\"},
    0x31: {\"name\": \"SNMP\", \"unique\": True, \"desc\": \"SNMP agent\"},
    0x43: {\"name\": \"Service\", \"unique\": True, \"desc\": \"Unknown\"},
    0x44: {\"name\": \"Service\", \"unique\": True, \"desc\": \"Unknown\"},
    0x45: {\"name\": \"Service\", \"unique\": True, \"desc\": \"Unknown\"},
    0x46: {\"name\": \"Service\", \"unique\": True, \"desc\": \"Unknown\"},
    0x47: {\"name\": \"Service\", \"unique\": True, \"desc\": \"Unknown\"},
    0x48: {\"name\": \"Service\", \"unique\": True, \"desc\": \"Unknown\"},
    0x49: {\"name\": \"Service\", \"unique\": True, \"desc\": \"Unknown\"},
    0x4B: {\"name\": \"Service\", \"unique\": True, \"desc\": \"Unknown\"},
    0x4C: {\"name\": \"Service\", \"unique\": True, \"desc\": \"Unknown\"},
    0x4D: {\"name\": \"Service\", \"unique\": True, \"desc\": \"Unknown\"},
    0x4E: {\"name\": \"Service\", \"unique\": True, \"desc\": \"Unknown\"},
    0x4F: {\"name\": \"Service\", \"unique\": True, \"desc\": \"Unknown\"},
    0x50: {\"name\": \"Service\", \"unique\": True, \"desc\": \"Unknown\"},
    0x51: {\"name\": \"Service\", \"unique\": True, \"desc\": \"Unknown\"},
    0x52: {\"name\": \"Service\", \"unique\": True, \"desc\": \"Unknown\"},
    0x53: {\"name\": \"Service\", \"unique\": True, \"desc\": \"Unknown\"},
    0x54: {\"name\": \"Service\", \"unique\": True, \"desc\": \"Unknown\"},
    0x55: {\"name\": \"Service\", \"unique\": True, \"desc\": \"Unknown\"},
    0x56: {\"name\": \"Service\", \"unique\": True, \"desc\": \"Unknown\"},
    0x57: {\"name\": \"Service\", \"unique\": True, \"desc\": \"Unknown\"},
    0x58: {\"name\": \"Service\", \"unique\": True, \"desc\": \"Unknown\"},
    0x59: {\"name\": \"Service\", \"unique\": True, \"desc\": \"Unknown\"},
    0x6B: {\"name\": \"Service\", \"unique\": True, \"desc\": \"Unknown\"},
    0x70: {\"name\": \"Service\", \"unique\": True, \"desc\": \"Unknown\"},
    0x81: {\"name\": \"Service\", \"unique\": True, \"desc\": \"Unknown\"},
}
`

---

*End of Document*
