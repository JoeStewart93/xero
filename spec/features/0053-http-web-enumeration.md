# F0053: HTTP/Web Enumeration

## Metadata
| Field | Value |
|---|---|
| ID | F0053 |
| Priority | P0 |
| Status | Planned |
| MVP Phase | 3 |
| Depends on | F0016, F0023, F0069 |

## Summary
Comprehensive web application discovery and enumeration including directory brute-forcing, technology detection, virtual host enumeration, and HTTP method probing. Uses bundled wordlists with support for custom wordlist downloads.

## Requirements
- Directory/file brute-forcing (gobuster-style)
- Technology detection (Wappalyzer-style fingerprints)
- Virtual host enumeration
- HTTP method probing (OPTIONS, PUT, TRACE)
- Subdomain takeover detection
- Configurable wordlists (bundled + downloadable)
- Concurrent scanning with rate limiting
- Results create web application assets

## Module Arguments

`python
{
    \"targets\": [\"http://192.168.1.100\", \"https://example.com\"],
    \"enum_types\": [\"directories\", \"tech_detect\", \"vhosts\", \"methods\"],
    \"wordlist\": \"common\",  # common, medium, large, or custom path
    \"wordlist_download\": \"https://example.com/custom.txt\",  // Optional download
    \"extensions\": [\".php\", \".asp\", \".bak\"],  // For directory enum
    \"threads\": 20,
    \"rate_limit\": \"10/s\",
    \"exclude_status\": [403, 404],
    \"follow_redirects\": true,
    \"headers\": {\"Authorization\": \"Bearer token\"},  // Optional auth
    \"execution_target\": \"auto\"
}
`

## Bundled Wordlists

| Wordlist | Size | Purpose |
| :--- | :--- | :--- |
| common-directories.txt | ~1k | Common paths (/admin, /login, etc.) |
| medium-directories.txt | ~10k | Extended path list |
| large-directories.txt | ~50k | Comprehensive list |
| subdomain-common.txt | ~500 | Common subdomains |
| api-endpoints.txt | ~200 | Common API paths |
| user-agents.txt | ~50 | User-Agent strings |

## Result Schema

`json
{
    \"target\": \"https://example.com\",
    \"scan_time\": \"2024-01-15T10:30:00Z\",
    \"technology\": {
        \"server\": \"nginx/1.18.0\",
        \"cms\": \"WordPress 6.2\",
        \"framework\": \"PHP 7.4\",
        \"analytics\": [\"Google Analytics\", \"Google Tag Manager\"],
        \"cdn\": \"Cloudflare\",
        \"javascript_libraries\": [\"jQuery 3.6.0\", \"Bootstrap 5.1\"],
        \"confidence_scores\": {
            \"WordPress\": 0.95,
            \"nginx\": 0.98
        }
    },
    \"directories\": [
        {
            \"path\": \"/admin\",
            \"url\": \"https://example.com/admin\",
            \"status\": 200,
            \"size\": 1234,
            \"redirect\": null,
            \"title\": \"Admin Login\",
            \"content_type\": \"text/html\"
        },
        {
            \"path\": \"/wp-config.php.bak\",
            \"url\": \"https://example.com/wp-config.php.bak\",
            \"status\": 200,
            \"size\": 567,
            \"sensitive\": true,
            \"title\": null
        },
        {
            \"path\": \"/api/v1/users\",
            \"url\": \"https://example.com/api/v1/users\",
            \"status\": 200,
            \"content_type\": \"application/json\",
            \"api_endpoint\": true
        }
    ],
    \"vhosts\": [
        {
            \"hostname\": \"dev.example.com\",
            \"ip\": \"192.168.1.100\",
            \"status\": 200,
            \"title\": \"Development Site\",
            \"server\": \"Apache/2.4.41\",
            \"different_response\": true
        },
        {
            \"hostname\": \"mail.example.com\",
            \"ip\": \"192.168.1.100\",
            \"status\": 200,
            \"title\": \"Webmail\",
            \"certificate_mismatch\": true
        }
    ],
    \"methods\": {
        \"GET\": {\"supported\": true, \"status\": 200},
        \"POST\": {\"supported\": true, \"status\": 200},
        \"PUT\": {\"supported\": true, \"status\": 200},  // Potential misconfiguration
        \"DELETE\": {\"supported\": false, \"status\": 405},
        \"PATCH\": {\"supported\": false, \"status\": 405},
        \"TRACE\": {\"supported\": true, \"status\": 200},  // XSS risk
        \"OPTIONS\": {\"supported\": true, \"cors_headers\": {...}}
    },
    \"headers\": {
        \"present\": {
            \"Server\": \"nginx/1.18.0\",
            \"X-Powered-By\": \"PHP/7.4\",
            \"Content-Type\": \"text/html\"
        },
        \"missing_security\": [
            \"X-Frame-Options\",
            \"Content-Security-Policy\",
            \"X-Content-Type-Options\",
            \"Strict-Transport-Security\"
        ],
        \"cors\": {
            \"access_control_allow_origin\": \"*\",
            \"access_control_allow_methods\": [\"GET\", \"POST\"],
            \"wildcard_origin\": true  // Potential issue
        }
    },
    \"subdomain_takeover_risk\": [
        {
            \"subdomain\": \"blog.example.com\",
            \"cname\": \"ghost.pages.dev\",
            \"risk\": \"medium\",
            \"service\": \"Ghost\",
            \"reason\": \"CNAME points to unclaimed service\"
        }
    ],
    \"summary\": {
        \"directories_found\": 15,
        \"vhosts_found\": 3,
        \"sensitive_files\": 2,
        \"api_endpoints\": 5,
        \"security_issues\": 4
    }
}
`

## Technology Detection Fingerprints

Detection methods:
1. **HTTP Headers**: Server, X-Powered-By, X-AspNet-Version
2. **HTML Meta Tags**: generator, viewport
3. **JavaScript Files**: Unique filenames/paths
4. **CSS Files**: Framework-specific paths
5. **Cookies**: Session cookie names
6. **Default Files**: README, default index pages

## Stages

### Stage 1: HTTP Enum Module Backend
**Goal:** Register http_enum in module registry with schema.
**Acceptance Criteria:**
- [ ] Module registered as uiltin.recon.http_enum
- [ ] Args validation for targets, enum_types, wordlist
- [ ] Wordlist path resolution (bundled vs custom)
- [ ] Module metadata exposed in /api/v1/modules

### Stage 2: Directory Brute-forcing
**Goal:** Implement directory/file discovery.
**Acceptance Criteria:**
- [ ] gobuster integration or pure Python implementation
- [ ] Wordlist loading from bundled or custom path
- [ ] Extension appending for file discovery
- [ ] Status code filtering
- [ ] Concurrent requests with rate limiting

### Stage 3: Technology Detection
**Goal:** Detect web technologies and frameworks.
**Acceptance Criteria:**
- [ ] HTTP header analysis
- [ ] HTML content fingerprinting
- [ ] JavaScript/CSS file detection
- [ ] Confidence scoring for detections
- [ ] CMS/version identification

### Stage 4: Vhost & Method Probing
**Goal:** Virtual host and HTTP method enumeration.
**Acceptance Criteria:**
- [ ] Vhost wordlist iteration
- [ ] Response comparison for unique hosts
- [ ] Certificate mismatch detection
- [ ] HTTP method probing (GET, POST, PUT, etc.)
- [ ] CORS header analysis

### Stage 5: Asset Integration
**Goal:** Create web application assets.
**Acceptance Criteria:**
- [ ] Web app assets created for targets
- [ ] Discovered directories linked to app
- [ ] Technology stack recorded
- [ ] Security issues flagged

## Feature Acceptance Criteria

- [ ] Directory brute-forcing finds known paths
- [ ] Technology detection accuracy > 90%
- [ ] Vhost enumeration finds misconfigured hosts
- [ ] HTTP method probing identifies misconfigurations
- [ ] Results create web application assets
- [ ] Wordlist download before scan works

## Test Plan

### Unit Tests
- [ ] test_http_enum_args_validation
- [ ] test_wordlist_path_resolution
- [ ] test_technology_fingerprint_matching
- [ ] test_status_code_filtering
- [ ] test_rate_limiter
- [ ] test_vhost_response_comparison

### System / Integration Tests
- [ ] Directory enum finds known paths on lab target
- [ ] Technology detection identifies WordPress correctly
- [ ] Vhost enum finds misconfigured virtual hosts
- [ ] Method probing identifies PUT/TRACE support
- [ ] CORS headers analyzed correctly
- [ ] Results create web app assets

### Playwright Tests
- [ ] HTTP Enum module visible in Recon module browser
- [ ] Enum type checkboxes available
- [ ] Wordlist dropdown shows options
- [ ] Submit scan task with valid target
- [ ] Results show technology stack
- [ ] Directories listed with status codes
- [ ] Security issues highlighted

## Directory Enumeration Implementation

`python
import aiohttp
from typing import Set

async def enumerate_directories(
    base_url: str,
    wordlist_path: str,
    extensions: list[str] = None,
    threads: int = 20,
    exclude_status: Set[int] = None,
) -> list[dict]:
    \"\"\"Brute-force directories using wordlist.\"\"\"

    # Load wordlist
    words = load_wordlist(wordlist_path)

    # Add extensions
    if extensions:
        words = extend_with_extensions(words, extensions)

    async with aiohttp.ClientSession() as session:
        semaphore = asyncio.Semaphore(threads)
        tasks = []

        for word in words:
            url = f\"{base_url.strip('/')}/{word}\"
            tasks.append(probe_url(session, url, exclude_status, semaphore))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter successful responses
        found = [r for r in results if r and r.get(\"status\") not in exclude_status]
        return found

async def probe_url(
    session: aiohttp.ClientSession,
    url: str,
    exclude_status: Set[int],
    semaphore: asyncio.Semaphore,
) -> dict | None:
    \"\"\"Probe single URL and return result.\"\"\"
    async with semaphore:
        try:
            async with session.get(url, allow_redirects=False, timeout=5) as response:
                return {
                    \"path\": url.replace(base_url, \"\"),
                    \"url\": url,
                    \"status\": response.status,
                    \"size\": len(response.content),
                    \"redirect\": response.headers.get(\"Location\"),
                    \"content_type\": response.content_type,
                }
        except asyncio.TimeoutError:
            return None
        except Exception:
            return None

def load_wordlist(path: str) -> list[str]:
    \"\"\"Load wordlist from file.\"\"\"
    with open(path, \"r\") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith(\"#\")]

def extend_with_extensions(words: list[str], extensions: list[str]) -> list[str]:
    \"\"\"Add file extensions to wordlist entries.\"\"\"
    extended = list(words)  # Keep original
    for word in words:
        for ext in extensions:
            extended.append(f\"{word}{ext}\")
    return extended
`

## Security Headers Checklist

| Header | Purpose | Risk if Missing |
| :--- | :--- | :--- |
| X-Frame-Options | Clickjacking protection | Medium |
| Content-Security-Policy | XSS protection | High |
| X-Content-Type-Options | MIME sniffing | Low |
| Strict-Transport-Security | HTTPS enforcement | Medium |
| X-XSS-Protection | Legacy XSS filter | Low |
| Referrer-Policy | Referrer leakage | Low |

---

*End of Document*
