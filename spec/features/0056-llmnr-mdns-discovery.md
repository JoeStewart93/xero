# F0056: LLMNR/mDNS Discovery

## Metadata
| Field | Value |
|---|---|
| ID | F0056 |
| Priority | P0 |
| Status | Planned |
| MVP Phase | 3 |
| Depends on | F0016, F0069 |

## Summary
Link-Local Multicast Name Resolution (LLMNR) and Multicast DNS (mDNS) discovery for local network participant enumeration. Primary execution target is beacon-side for optimal network position. Discovers Windows and macOS/Linux hosts on the local subnet.

## Requirements
- LLMNR name query responses (Windows)
- mDNS service discovery (Avahi/Bonjour)
- Network participant enumeration
- Primary execution on beacons (network position)
- Interface selection for multi-homed hosts
- Integration with asset inventory

## Module Arguments

`python
{
    \"interface\": \"eth0\",  // or \"all\"
    \"enum_types\": [\"llmnr_query\", \"mdns_browse\", \"mdns_query\"],
    \"llmnr_names\": [\"WORKSTATION\", \"SERVER\"],  // Optional specific names
    \"mdns_services\": [\"_http._tcp\", \"_ssh._tcp\", \"_smb._tcp\"],  // Optional
    \"timeout_seconds\": 30,
    \"execution_target\": \"beacon\"  // Primary - needs network position
}
`

## LLMNR Protocol

LLMNR (RFC 4795) is used by Windows for name resolution when DNS fails:
- Multicast address: 224.0.0.252
- UDP port: 5355
- Query types: A, AAAA, CNAME, PTR

## mDNS Protocol

mDNS (RFC 6762) is used by macOS/Linux and some Windows:
- Multicast address: 224.0.0.251
- UDP port: 5353
- Service types: _http._tcp, _ssh._tcp, _smb._tcp, etc.

## Result Schema

`json
{
    \"interface\": \"eth0\",
    \"scan_time\": \"2024-01-15T10:30:00Z\",
    \"llmnr_responses\": [
        {
            \"hostname\": \"WORKSTATION\",
            \"fqdn\": \"WORKSTATION.local\",
            \"ip\": \"192.168.1.105\",
            \"mac\": \"AA:BB:CC:DD:EE:FF\",
            \"ttl\": 120,
            \"query_type\": \"A\",
            \"response_time_ms\": 15
        },
        {
            \"hostname\": \"SERVER\",
            \"fqdn\": \"SERVER.local\",
            \"ip\": \"192.168.1.10\",
            \"mac\": \"11:22:33:44:55:66\",
            \"ttl\": 120,
            \"query_type\": \"A\",
            \"response_time_ms\": 12
        }
    ],
    \"mdns_hosts\": [
        {
            \"hostname\": \"macbook-pro.local\",
            \"fqdn\": \"macbook-pro.local\",
            \"ip\": \"192.168.1.110\",
            \"txt_records\": {
                \"version\": \"2.0\",
                \"type\": \"MacBookPro16,1\"
            }
        }
    ],
    \"mdns_services\": [
        {
            \"hostname\": \"macbook-pro.local\",
            \"name\": \"macbook-pro\",
            \"service_type\": \"_http._tcp\",
            \"port\": 8080,
            \"ip\": \"192.168.1.110\",
            \"txt_records\": {
                \"path\": \"/\",
                \"encrypt\": \"none\",
                \"version\": \"Apache/2.4.41\"
            }
        },
        {
            \"hostname\": \"raspberrypi.local\",
            \"name\": \"raspberrypi\",
            \"service_type\": \"_ssh._tcp\",
            \"port\": 22,
            \"ip\": \"192.168.1.120\",
            \"txt_records\": {
                \"version\": \"OpenSSH_8.2p1\"
            }
        },
        {
            \"hostname\": \"fileserver.local\",
            \"name\": \"fileserver\",
            \"service_type\": \"_smb._tcp\",
            \"port\": 445,
            \"ip\": \"192.168.1.100\",
            \"txt_records\": {}
        }
    ],
    \"summary\": {
        \"llmnr_hosts\": 2,
        \"mdns_hosts\": 1,
        \"mdns_services\": 3,
        \"unique_ips\": 4
    }
}
`

## Common mDNS Service Types

| Service Type | Port | Protocol | Description |
| :--- | :--- | :--- | :--- |
| _http._tcp | 80 | TCP | HTTP Web Server |
| _https._tcp | 443 | TCP | HTTPS Web Server |
| _ssh._tcp | 22 | TCP | SSH Server |
| _smb._tcp | 445 | TCP | SMB File Sharing |
| _ftp._tcp | 21 | TCP | FTP Server |
| _telnet._tcp | 23 | TCP | Telnet Server |
| _ldap._tcp | 389 | TCP | LDAP Directory |
| _mysql._tcp | 3306 | TCP | MySQL Database |
| _postgresql._tcp | 5432 | TCP | PostgreSQL Database |
| _ipp._tcp | 631 | TCP | IPP Printer |

## Stages

### Stage 1: LLMNR/mDNS Module Backend
**Goal:** Register llmnr_mdns module with schema.
**Acceptance Criteria:**
- [ ] Module registered as uiltin.recon.llmnr_mdns
- [ ] Args validation for interface, enum_types
- [ ] Module metadata exposed in /api/v1/modules
- [ ] Beacon-side execution support

### Stage 2: LLMNR Discovery
**Goal:** Query LLMNR for Windows hosts.
**Acceptance Criteria:**
- [ ] LLMNR multicast query sent
- [ ] Responses parsed for hostname/IP/MAC
- [ ] Timeout handling
- [ ] Multiple name queries supported

### Stage 3: mDNS Discovery
**Goal:** Browse mDNS for services and hosts.
**Acceptance Criteria:**
- [ ] mDNS browse for service types
- [ ] Service records parsed
- [ ] TXT record extraction
- [ ] Host record extraction

### Stage 4: Beacon Integration
**Goal:** Execute from beacon on target network.
**Acceptance Criteria:**
- [ ] Beacon plugin for LLMNR/mDNS
- [ ] Interface selection on beacon
- [ ] Results returned to C2
- [ ] Asset creation from results

## Feature Acceptance Criteria

- [ ] LLMNR queries receive responses from Windows hosts
- [ ] mDNS browse discovers local services
- [ ] Works from beacon on target network
- [ ] Results create host assets
- [ ] Service information extracted

## Test Plan

### Unit Tests
- [ ] test_llmnr_mdns_args_validation
- [ ] test_llmnr_packet_construction
- [ ] test_mdns_packet_construction
- [ ] test_response_parsing
- [ ] test_txt_record_parsing

### System / Integration Tests
- [ ] LLMNR query receives response from Windows host
- [ ] mDNS browse discovers HTTP service
- [ ] mDNS browse discovers SSH service
- [ ] Beacon execution returns results
- [ ] Results create host assets
- [ ] Timeout handled for no responses

### Playwright Tests
- [ ] LLMNR/mDNS module visible in Recon module browser
- [ ] Interface selection available
- [ ] Submit task from beacon context
- [ ] Results show discovered hosts
- [ ] Services listed with ports

## LLMNR Implementation

`python
import socket
import struct
from scapy.all import UDP, IP, sr1, Raw

def llmnr_query(name: str, interface: str = None) -> dict | None:
    \"\"\"Send LLMNR query and parse response.\"\"\"

    # LLMNR query packet
    llmnr_query_packet = bytes([
        0x00,  # Query type (Q)
        0x01,  # QTYPE: Host (A record)
        0x00,  # Reserved
        0x00,  # Reserved
    ])

    # Encode name (NBNS format)
    name_bytes = name.encode('utf-16-le')
    name_length = len(name_bytes)
    llmnr_query_packet += struct.pack('>H', name_length)
    llmnr_query_packet += name_bytes

    # Build packet
    dst_ip = \"224.0.0.252\"
    dst_port = 5355

    pkt = IP(dst=dst_ip)/UDP(dport=dst_port, sport=5355)/Raw(load=llmnr_query_packet)

    try:
        # Send and receive
        if interface:
            resp = sr1(pkt, timeout=5, iface=interface, verbose=0)
        else:
            resp = sr1(pkt, timeout=5, verbose=0)

        if resp:
            return parse_llmnr_response(resp)

    except Exception as e:
        pass

    return None

def parse_llmnr_response(response) -> dict:
    \"\"\"Parse LLMNR response packet.\"\"\"
    result = {}

    try:
        # Extract payload
        payload = bytes(response[Raw].load)

        # Parse response type
        resp_type = payload[0]
        if resp_type == 0x80:  # Response
            # Parse name
            name_length = struct.unpack('>H', payload[4:6])[0]
            name = payload[6:6+name_length].decode('utf-16-le', errors='ignore')
            result[\"hostname\"] = name

            # Parse resource records
            # ... (simplified)

    except Exception:
        pass

    return result

def llmnr_sweep(interface: str = None, timeout: int = 30) -> list[dict]:
    \"\"\"Sweep for LLMNR responders.\"\"\"
    results = []

    # Common names to query
    names = [
        \"WORKGROUP\", \"DOMAIN\", \"SERVER\", \"WORKSTATION\",
        \"FILESERVER\", \"PRINTSERVER\", \"DC\", \"PDC\",
    ]

    for name in names:
        response = llmnr_query(name, interface)
        if response:
            results.append(response)

    return results
`

## mDNS Implementation

`python
from scapy.all import UDP, IP, sr1, Raw
import struct

def mdns_browse(service_type: str = None, interface: str = None) -> list[dict]:
    \"\"\"Browse mDNS for services.\"\"\"

    results = []

    # mDNS browse query
    dst_ip = \"224.0.0.251\"
    dst_port = 5353

    # Query for all services if no specific type
    if not service_type:
        service_type = \"_services._dns-sd._udp.local.\"

    # Build mDNS query
    mdns_query = build_mdns_query(service_type)

    pkt = IP(dst=dst_ip)/UDP(dport=dst_port, sport=5353)/Raw(load=mdns_query)

    try:
        if interface:
            resp = sr1(pkt, timeout=5, iface=interface, verbose=0)
        else:
            resp = sr1(pkt, timeout=5, verbose=0)

        if resp:
            results = parse_mdns_response(resp)

    except Exception:
        pass

    return results

def build_mdns_query(service_type: str) -> bytes:
    \"\"\"Build mDNS query packet.\"\"\"
    # Simplified mDNS query construction
    # In practice, use a library like zeroconf

    query = b''

    # Header (12 bytes)
    query += struct.pack('>HHHHHH', 0, 0x8180, 1, 0, 0, 0)

    # Question section
    query += encode_mdns_name(service_type)
    query += struct.pack('>HH', 0x001C, 1)  # TYPE=PTR, CLASS=IN

    return query

def encode_mdns_name(name: str) -> bytes:
    \"\"\"Encode mDNS name.\"\"\"
    if not name.endswith('.'):
        name += '.'

    encoded = b''
    for label in name.split('.'):
        if label:
            encoded += bytes([len(label)]) + label.encode()
    encoded += b'\\x00'

    return encoded

def parse_mdns_response(response) -> list[dict]:
    \"\"\"Parse mDNS response packet.\"\"\"
    results = []

    try:
        payload = bytes(response[Raw].load)

        # Parse mDNS response
        # ... (simplified)
        # Use zeroconf library for production

    except Exception:
        pass

    return results
`

## Beacon-Side Implementation

`python
# Beacon plugin for LLMNR/mDNS
class BeaconLLMNRModule:
    name = \"llmnr_mdns_discovery\"
    description = \"Discover local hosts via LLMNR/mDNS\"

    def execute(self, args: dict, callback: Callable) -> dict:
        interface = args.get(\"interface\", \"all\")
        enum_types = args.get(\"enum_types\", [\"llmnr_query\", \"mdns_browse\"])

        results = {\"interface\": interface, \"llmnr_responses\": [], \"mdns_services\": []}

        if \"llmnr_query\" in enum_types:
            results[\"llmnr_responses\"] = llmnr_sweep(interface)

        if \"mdns_browse\" in enum_types:
            results[\"mdns_services\"] = mdns_browse(interface=interface)

        return results
`

---

*End of Document*
