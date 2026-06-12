# F0052: Whois Domain Lookup

## Metadata
| Field | Value |
|---|---|
| ID | F0052 |
| Priority | P0 |
| Status | Planned |
| MVP Phase | 3 |
| Depends on | F0037, F0069 |

## Summary
Domain registration intelligence gathering via whois protocol. Extracts registrar information, name servers, creation/expiration dates, and contact details. Supports multiple TLDs with automatic whois server detection.

## Requirements
- Domain whois queries via python-whois library
- Support for common TLDs (.com, .net, .org, .io, etc.)
- Automatic whois server detection
- Rate limiting to avoid server blocking
- Structured result parsing
- Integration with DNS enumeration (F0037)
- Asset creation for discovered domains

## Module Arguments

`python
{
    \"domains\": [\"example.com\", \"target.org\"],
    \"include_nameservers\": true,
    \"include_contacts\": true,
    \"include_raw\": false,  # Include raw whois output
    \"timeout_seconds\": 30,
    \"rate_limit_delay_ms\": 500,  # Delay between queries
    \"execution_target\": \"auto\"
}
`

## Result Schema

`json
{
    \"domain\": \"example.com\",
    \"query_time\": \"2024-01-15T10:30:00Z\",
    \"registrar\": {
        \"name\": \"Example Registrar Inc.\",
        \"url\": \"https://www.exampleregistrar.com\",
        \"iana_id\": \"1234\"
    },
    \"dates\": {
        \"creation_date\": \"2020-01-15T00:00:00Z\",
        \"expiration_date\": \"2025-01-15T00:00:00Z\",
        \"updated_date\": \"2024-01-10T00:00:00Z\",
        \"registry_expiry_date\": \"2025-01-15T00:00:00Z\"
    },
    \"status\": [
        \"clientTransferProhibited\",
        \"clientUpdateProhibited\",
        \"clientDeleteProhibited\"
    ],
    \"nameservers\": [
        {\"name\": \"ns1.example.com\", \"ip\": \"192.0.2.1\"},
        {\"name\": \"ns2.example.com\", \"ip\": \"192.0.2.2\"}
    ],
    \"dnssec\": \"unsigned\",  // unsigned, signedDelegation, unsignedDS
    \"contacts\": {
        \"registrant\": {
            \"name\": \"John Doe\",
            \"organization\": \"Example Corp\",
            \"street\": \"123 Example St\",
            \"city\": \"New York\",
            \"state\": \"NY\",
            \"postal_code\": \"10001\",
            \"country\": \"US\",
            \"phone\": \"+1.5555555555\",
            \"fax\": \"+1.5555555556\",
            \"email\": \"admin@example.com\"
        },
        \"admin\": {...},
        \"tech\": {...},
        \"billing\": {...}
    },
    \"emails_extracted\": [\"admin@example.com\", \"tech@example.com\"],
    \"raw_whois\": \"...\"  // Optional full raw output
}
`

## Status Code Meanings

| Status | Meaning |
| :--- | :--- |
| clientTransferProhibited | Domain transfer disabled |
| clientUpdateProhibited | Domain update disabled |
| clientDeleteProhibited | Domain deletion disabled |
| serverTransferProhibited | Server-level transfer lock |
| ok | Normal status |
| inactive | Domain inactive |

## Stages

### Stage 1: Whois Module Backend
**Goal:** Register whois in module registry with schema.
**Acceptance Criteria:**
- [ ] Module registered as uiltin.recon.whois
- [ ] Args validation for domains list
- [ ] Rate limiting configuration
- [ ] Module metadata exposed in /api/v1/modules

### Stage 2: Whois Query Execution
**Goal:** Execute whois queries with error handling.
**Acceptance Criteria:**
- [ ] python-whois library integration
- [ ] Automatic whois server detection
- [ ] Timeout handling per query
- [ ] Rate limiting between queries
- [ ] Error handling for unreachable servers

### Stage 3: Result Parsing
**Goal:** Normalize whois output across TLDs.
**Acceptance Criteria:**
- [ ] Date parsing handles multiple formats
- [ ] Contact information extracted consistently
- [ ] Name servers parsed with IP resolution
- [ ] Email addresses extracted for enrichment

### Stage 4: Asset Integration
**Goal:** Create domain assets and link to DNS results.
**Acceptance Criteria:**
- [ ] Domain assets created for queried domains
- [ ] Name servers added as related assets
- [ ] Email addresses extracted for reporting
- [ ] Integration with DNS enumeration results

## Feature Acceptance Criteria

- [ ] Whois queries return structured data for common TLDs
- [ ] Rate limiting prevents server blocking
- [ ] Error handling for unreachable whois servers
- [ ] Contact emails extracted for enrichment
- [ ] Domain assets created in inventory
- [ ] Results link to DNS enumeration

## Test Plan

### Unit Tests
- [ ] test_whois_args_validation
- [ ] test_domain_list_validation
- [ ] test_date_parsing_multiple_formats
- [ ] test_contact_extraction
- [ ] test_email_extraction
- [ ] test_rate_limiter

### System / Integration Tests
- [ ] Whois query for .com domain succeeds
- [ ] Whois query for .org domain succeeds
- [ ] Whois query for .io domain succeeds
- [ ] Rate limiting enforced between queries
- [ ] Timeout handled for slow servers
- [ ] Error returned for non-existent domain

### Playwright Tests
- [ ] Whois module visible in Recon module browser
- [ ] Submit whois task with valid domains
- [ ] Results show registrar and dates
- [ ] Contact information displayed (if included)
- [ ] Domain asset created in inventory

## Whois Query Implementation

`python
import whois
from datetime import datetime

def query_whois(domain: str, timeout: int = 30) -> dict:
    \"\"\"Query whois for a single domain.\"\"\"
    try:
        w = whois.whois(domain)

        return {
            \"domain\": domain,
            \"query_time\": datetime.utcnow().isoformat(),
            \"registrar\": {
                \"name\": w.registrar,
                \"url\": getattr(w, \"registrar_url\", None),
                \"iana_id\": getattr(w, \"registrar_iana_id\", None),
            },
            \"dates\": {
                \"creation_date\": format_date(w.creation_date),
                \"expiration_date\": format_date(w.expiration_date),
                \"updated_date\": format_date(w.updated_date),
            },
            \"status\": w.status if isinstance(w.status, list) else [w.status] if w.status else [],
            \"nameservers\": w.nameservers if isinstance(w.nameservers, list) else [w.nameservers] if w.nameservers else [],
            \"dnssec\": getattr(w, \"dnssec\", \"unknown\"),
            \"contacts\": extract_contacts(w),
            \"emails_extracted\": extract_emails(w),
        }
    except whois.WhoisError as e:
        return {
            \"domain\": domain,
            \"error\": str(e),
            \"query_time\": datetime.utcnow().isoformat(),
        }

def format_date(date) -> str | None:
    \"\"\"Normalize date to ISO format.\"\"\"
    if date is None:
        return None

    if isinstance(date, list):
        date = date[0] if date else None

    if isinstance(date, datetime):
        return date.isoformat()

    if isinstance(date, str):
        # Try common formats
        for fmt in [\"%Y-%m-%d\", \"%d-%m-%Y\", \"%m/%d/%Y\", \"%d/%m/%Y\"]:
            try:
                return datetime.strptime(date, fmt).isoformat()
            except ValueError:
                continue
        return date  # Return as-is if parsing fails

    return str(date)

def extract_contacts(w) -> dict:
    \"\"\"Extract contact information from whois object.\"\"\"
    contacts = {}

    for contact_type in [\"registrant\", \"admin\", \"tech\", \"billing\"]:
        contact_attr = getattr(w, f\"{contact_type}_name\", None)
        if contact_attr or any([
            getattr(w, f\"{contact_type}_organization\", None),
            getattr(w, f\"{contact_type}_email\", None),
        ]):
            contacts[contact_type] = {
                \"name\": getattr(w, f\"{contact_type}_name\", None),
                \"organization\": getattr(w, f\"{contact_type}_organization\", None),
                \"email\": getattr(w, f\"{contact_type}_email\", None),
                \"phone\": getattr(w, f\"{contact_type}_phone\", None),
                \"country\": getattr(w, f\"{contact_type}_country\", None),
            }

    return contacts

def extract_emails(w) -> list[str]:
    \"\"\"Extract all email addresses from whois object.\"\"\"
    emails = set()

    # Check common email attributes
    for attr in dir(w):
        if \"email\" in attr.lower():
            value = getattr(w, attr, None)
            if value:
                if isinstance(value, list):
                    emails.update(str(e).lower() for e in value)
                else:
                    emails.add(str(value).lower())

    return list(emails)
`

## Rate Limiting

Different TLDs have different rate limits:
- .com/.net/.org: ~1 query/second
- .io: ~1 query/2 seconds
- Country TLDs: Varies widely

Default rate limit: 500ms between queries

`python
async def query_whois_batch(domains: list[str], delay_ms: int = 500) -> list[dict]:
    results = []
    for domain in domains:
        result = await asyncio.to_thread(query_whois, domain)
        results.append(result)
        await asyncio.sleep(delay_ms / 1000.0)
    return results
`

---

*End of Document*
