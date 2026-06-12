# F0054: Shodan/Censys Enrichment

## Metadata
| Field | Value |
|---|---|
| ID | F0054 |
| Priority | P0 |
| Status | Planned |
| MVP Phase | 3 |
| Depends on | F0023, F0030, F0069, F0070 |

## Summary
External threat intelligence enrichment via Shodan and Censys APIs. Provides historical data, banner matching, vulnerability information, and exposed service discovery. Requires API keys configured via F0070.

## Requirements
- Shodan API integration (host, domain, CIDR queries)
- Censys API integration (hosts, certificates)
- API key management via F0070
- Result caching to minimize API calls
- Historical data retrieval
- CVE/vulnerability extraction
- Integration with asset inventory

## Module Arguments

`python
{
    \"targets\": [\"192.168.1.100\", \"example.com\", \"10.0.0.0/24\"],
    \"providers\": [\"shodan\", \"censys\"],
    \"lookup_types\": [\"host\", \"ports\", \"certificates\", \"vulns\", \"history\"],
    \"include_raw_banners\": false,
    \"execution_target\": \"auto\"  // beacon not useful for external APIs
}
`

## Shodan API Endpoints Used

| Endpoint | Purpose | Rate Limit |
| :--- | :--- | :--- |
| /shodan/host/{ip} | Host information | 1/sec |
| /shodan/domain/{domain} | Domain enumeration | 1/sec |
| /shodan/count/{query} | Search count | 1/sec |
| /shodan/search?key={query} | Search results | 1/sec |
| /shodan/cve/{cve} | CVE details | 1/sec |

## Censys API Endpoints Used

| Endpoint | Purpose | Rate Limit |
| :--- | :--- | :--- |
| /v1/hosts/{ip} | Host information | 5/sec |
| /v1/certificates/{cert_id} | Certificate details | 5/sec |
| /v2/search/hosts | Search hosts | 5/sec |

## Result Schema

`json
{
    \"target\": \"192.168.1.100\",
    \"query_time\": \"2024-01-15T10:30:00Z\",
    \"shodan\": {
        \"hostnames\": [\"server1.example.com\", \"web.example.com\"],
        \"ip\": \"192.168.1.100\",
        \"ports\": [22, 80, 443, 3306],
        \"tags\": [\"ssl\", \"web-server\", \"database\", \"cdn\"],
        \"os\": \"Linux\",
        \"org\": \"Example Corp\",
        \"isp\": \"Example ISP\",
        \"country_code\": \"US\",
        \"city\": \"New York\",
        \"last_update\": \"2024-01-14T08:00:00Z\",
        \"vulns\": [
            {
                \"cve\": \"CVE-2021-44228\",
                \"title\": \"Log4Shell Remote Code Execution\",
                \"severity\": \"critical\",
                \"cvss\": 10.0
            }
        ],
        \"services\": [
            {
                \"port\": 443,
                \"service\": \"https\",
                \"product\": \"nginx\",
                \"version\": \"1.18.0\",
                \"banner\": \"HTTP/1.1 200 OK\\r\\nServer: nginx/1.18.0...\",
                \"ssl\": {
                    \"cert\": \"CN=example.com\",
                    \"expires\": \"2024-12-31\"
                }
            }
        ],
        \"history\": [
            {
                \"timestamp\": \"2023-06-15T00:00:00Z\",
                \"ports\": [80, 443],
                \"different_from_current\": true
            }
        ]
    },
    \"censys\": {
        \"ip\": \"192.168.1.100\",
        \"services\": [
            {
                \"port\": 443,
                \"service\": \"TLS\",
                \"transport_protocol\": \"TCP\",
                \"tls\": {
                    \"certificates\": [
                        {
                            \"cert_chain\": [...],
                            \"leaf_data\": {
                                \"subject\": {\"CN\": \"example.com\"},
                                \"issuer\": {\"CN\": \"Let's Encrypt\"},
                                \"public_key\": {\"algorithm\": \"RSA\", \"bits\": 2048},
                                \"valid_not_after\": \"2024-12-31T23:59:59Z\",
                                \"valid_not_before\": \"2024-01-01T00:00:00Z\"
                            }
                        }
                    ],
                    \"cipher_suite\": \"TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384\",
                    \"ja3\": \"abc123...\"
                }
            }
        ],
        \"persistance\": {
            \"first_observed\": \"2020-01-01T00:00:00Z\",
            \"last_observed\": \"2024-01-15T00:00:00Z\",
            \"num_observations\": 156
        }
    },
    \"enriched_assets\": [
        {\"asset_id\": \"uuid\", \"type\": \"host\", \"enriched_fields\": [\"vulns\", \"hostnames\"]}
    ]
}
`

## Stages

### Stage 1: Shodan/Censys Module Backend
**Goal:** Register enrichment module with schema.
**Acceptance Criteria:**
- [ ] Module registered as uiltin.recon.enrichment
- [ ] Args validation for targets, providers
- [ ] API key retrieval from F0070
- [ ] Module metadata exposed in /api/v1/modules

### Stage 2: Shodan Integration
**Goal:** Implement Shodan API queries.
**Acceptance Criteria:**
- [ ] Host lookup via /shodan/host/{ip}
- [ ] Domain enumeration via /shodan/domain/{domain}
- [ ] Rate limiting (1 req/sec)
- [ ] API error handling
- [ ] Result caching

### Stage 3: Censys Integration
**Goal:** Implement Censys API queries.
**Acceptance Criteria:**
- [ ] Host lookup via /v1/hosts/{ip}
- [ ] Certificate details extraction
- [ ] Rate limiting (5 req/sec)
- [ ] API error handling
- [ ] Result caching

### Stage 4: Result Merging
**Goal:** Combine data from multiple providers.
**Acceptance Criteria:**
- [ ] Shodan and Censys results merged
- [ ] Duplicate services deduplicated
- [ ] Conflicting data resolved
- [ ] Vulnerabilities aggregated

### Stage 5: Asset Enrichment
**Goal:** Update assets with enrichment data.
**Acceptance Criteria:**
- [ ] Host assets updated with vulns
- [ ] Hostnames added to assets
- [ ] Service information enriched
- [ ] Geographic data added

## Feature Acceptance Criteria

- [ ] Shodan API queries return enriched data
- [ ] Censys API queries return service data
- [ ] API key errors handled gracefully
- [ ] Results merged with local scan data
- [ ] Assets enriched with external data
- [ ] Rate limiting prevents API quota exhaustion

## Test Plan

### Unit Tests
- [ ] test_enrichment_args_validation
- [ ] test_shodan_api_key_retrieval
- [ ] test_censys_api_key_retrieval
- [ ] test_rate_limiter_shodan
- [ ] test_rate_limiter_censys
- [ ] test_result_merging
- [ ] test_cache_hit_miss

### System / Integration Tests
- [ ] Shodan host lookup returns data
- [ ] Shodan domain enumeration works
- [ ] Censys host lookup returns data
- [ ] Certificate data extracted correctly
- [ ] Vulnerabilities aggregated from both sources
- [ ] API errors handled gracefully
- [ ] Cached results returned on repeat query

### Playwright Tests
- [ ] Enrichment module visible in Recon module browser
- [ ] Provider checkboxes available
- [ ] Submit enrichment task with valid targets
- [ ] Results show Shodan data
- [ ] Results show Censys data
- [ ] Vulnerabilities displayed with severity

## Shodan Implementation

`python
import shodan
from datetime import datetime, timedelta

class ShodanClient:
    def __init__(self, api_key: str):
        self.api = shodan.Shodan(api_key)
        self.cache = {}
        self.cache_ttl = timedelta(hours=24)

    async def lookup_host(self, ip: str) -> dict:
        \"\"\"Lookup host information via Shodan.\"\"\"
        cache_key = f\"shodan:host:{ip}\"

        # Check cache
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if datetime.now() - cached[\"timestamp\"] < self.cache_ttl:
                return cached[\"data\"]

        try:
            host = await asyncio.to_thread(self.api.host, ip)

            result = {
                \"hostnames\": host.get(\"hostnames\", []),
                \"ip\": host.get(\"ip_str\"),
                \"ports\": host.get(\"ports\", []),
                \"tags\": host.get(\"tags\", []),
                \"os\": host.get(\"os\"),
                \"org\": host.get(\"org\"),
                \"isp\": host.get(\"isp\"),
                \"country_code\": host.get(\"country_code\"),
                \"city\": host.get(\"city\"),
                \"last_update\": host.get(\"last_update\"),
                \"vulns\": host.get(\"vulns\", []),
                \"services\": self._parse_services(host.get(\"data\", [])),
            }

            # Cache result
            self.cache[cache_key] = {
                \"data\": result,
                \"timestamp\": datetime.now()
            }

            return result

        except shodan.APIError as e:
            return {\"error\": str(e), \"ip\": ip}

    def _parse_services(self, data: list) -> list[dict]:
        \"\"\"Parse Shodan service data.\"\"\"
        services = []
        for entry in data:
            service = {
                \"port\": entry.get(\"port\"),
                \"service\": entry.get(\"product\"),
                \"version\": entry.get(\"version\"),
                \"banner\": entry.get(\"data\"),
            }
            if \"ssl\" in entry:
                service[\"ssl\"] = entry[\"ssl\"]
            services.append(service)
        return services
`

## Censys Implementation

`python
import censys.ipv4
from datetime import datetime, timedelta

class CensysClient:
    def __init__(self, api_id: str, api_secret: str):
        self.api = censys.ipv4.CensysIPv4(api_id, api_secret)
        self.cache = {}
        self.cache_ttl = timedelta(hours=24)

    async def lookup_host(self, ip: str) -> dict:
        \"\"\"Lookup host information via Censys.\"\"\"
        cache_key = f\"censys:host:{ip}\"

        # Check cache
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if datetime.now() - cached[\"timestamp\"] < self.cache_ttl:
                return cached[\"data\"]

        try:
            host = await asyncio.to_thread(self.api.view, ip)

            result = {
                \"ip\": host.get(\"ip\"),
                \"services\": self._parse_services(host.get(\"services\", [])),
                \"persistance\": {
                    \"first_observed\": host.get(\"first_seen\"),
                    \"last_observed\": host.get(\"last_seen\"),
                    \"num_observations\": host.get(\"num_unique_data\"),
                }
            }

            # Cache result
            self.cache[cache_key] = {
                \"data\": result,
                \"timestamp\": datetime.now()
            }

            return result

        except Exception as e:
            return {\"error\": str(e), \"ip\": ip}

    def _parse_services(self, services: list) -> list[dict]:
        \"\"\"Parse Censys service data.\"\"\"
        parsed = []
        for service in services:
            parsed_service = {
                \"port\": service.get(\"port\"),
                \"transport_protocol\": service.get(\"transport_protocol\"),
            }

            if \"tls\" in service:
                parsed_service[\"tls\"] = {
                    \"certificates\": service[\"tls\"].get(\"certificates\", []),
                    \"cipher_suite\": service[\"tls\"].get(\"cipher_suite\"),
                    \"ja3\": service[\"tls\"].get(\"ja3_hash\"),
                }

            parsed.append(parsed_service)

        return parsed
`

## API Quota Management

| Provider | Free Tier | Paid Tier |
| :--- | :--- | :--- |
| Shodan | 1,000 queries/month | 10,000+/month |
| Censys | 5,000 queries/month | 50,000+/month |

Implement quota tracking:
`python
class APIQuotaTracker:
    def __init__(self):
        self.quotas = {
            \"shodan\": {\"limit\": 1000, \"used\": 0, \"reset_date\": None},
            \"censys\": {\"limit\": 5000, \"used\": 0, \"reset_date\": None},
        }

    def check_quota(self, provider: str) -> bool:
        quota = self.quotas.get(provider)
        if not quota:
            return True
        return quota[\"used\"] < quota[\"limit\"]

    def increment_usage(self, provider: str):
        self.quotas[provider][\"used\"] += 1
`

---

*End of Document*
