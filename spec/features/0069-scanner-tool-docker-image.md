# F0069: Scanner Tool Docker Image

## Metadata
| Field | Value |
|---|---|
| ID | F0069 |
| Priority | P0 |
| Status | Planned |
| MVP Phase | 3 |
| Depends on | F0045 |

## Summary
Unified Docker image for the scanner service with all reconnaissance tools pre-installed and configured. The image bundles industry-standard scanning tools (masscan, nmap, gobuster, etc.) alongside Python libraries for custom scanner modules. Container size target is ~500MB.

## Requirements
- Multi-stage Dockerfile minimizing final image size
- All scanner tools executable from container
- Health endpoint reporting tool availability
- Wordlists bundled for common enumeration tasks
- Configurable for additional wordlist downloads
- Tools available to both scanner service and C2 embedded scanner

## Bundled Tools

### System Tools
- masscan (fast port scanner)
- nmap (comprehensive network scanner)
- whois (domain lookup)
- dig, host (DNS queries)
- tcpdump (packet capture)

### Web Enumeration
- gobuster (directory brute-forcing)
- ffuf (fast web fuzzer)
- httpx (HTTP probing)
- subfinder (subdomain discovery)

### Python Libraries
- aiohttp, httpx (async HTTP clients)
- impacket (SMB/LDAP/NetBIOS)
- dnspython, dnslib (DNS operations)
- cryptography, pyopenssl (SSL/TLS analysis)
- python-whois (domain lookup)
- shodan, censys (enrichment APIs)
- beautifulsoup4, lxml (HTML parsing)

### Bundled Wordlists
- common-directories.txt (~1k entries)
- common-extensions.txt
- subdomain-common.txt (~500 entries)
- api-endpoints.txt
- user-agents.txt

## Stages

### Stage 1: Dockerfile Construction
**Goal:** Create multi-stage Dockerfile with all tools.
**Acceptance Criteria:**
- [ ] Base image: python:3.12-slim
- [ ] System tools installed via apt
- [ ] Python dependencies installed via pip
- [ ] Wordlists copied to /wordlists/
- [ ] Health check endpoint implemented
- [ ] Final image size < 500MB

### Stage 2: Tool Integration
**Goal:** Ensure all tools are executable and integrated.
**Acceptance Criteria:**
- [ ] masscan --help returns version
- [ ] nmap --version returns version
- [ ] gobuster version returns version
- [ ] Python modules importable
- [ ] Wordlists accessible at expected paths

### Stage 3: Health & Readiness
**Goal:** Scanner reports tool availability.
**Acceptance Criteria:**
- [ ] /health endpoint returns tool status
- [ ] /ready endpoint verifies all tools functional
- [ ] Missing tools reported in health response
- [ ] Docker healthcheck passes

## Feature Acceptance Criteria

- [ ] Scanner Docker builds successfully from Dockerfile
- [ ] All bundled tools executable from container
- [ ] Health endpoint returns tool availability
- [ ] Container size under 500MB
- [ ] Wordlists accessible for scanner modules

## Test Plan

### Unit Tests
- [ ] test_dockerfile_builds
- [ ] test_all_tools_executable
- [ ] test_wordlists_present
- [ ] test_health_endpoint_returns_tools
- [ ] test_image_size_under_limit

### System / Integration Tests
- [ ] Scanner container starts and passes healthcheck
- [ ] masscan scan executes from container
- [ ] nmap scan executes from container
- [ ] Python scanner modules import and execute

### Playwright Tests
- [ ] Scanner service appears healthy in Settings > Infrastructure
- [ ] Tool availability visible in UI (if exposed)

## Dockerfile Reference

`dockerfile
FROM python:3.12-slim AS base

# Install system tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    masscan \
    nmap \
    whois \
    dnsutils \
    tcpdump \
    gobuster \
    && rm -rf /var/lib/apt/lists/*

# Install ffuf, httpx, subfinder (download binaries)
RUN curl -sL https://github.com/ffuf/ffuf/releases/latest/download/ffuf_linux_amd64.tar.gz | tar xz -C /usr/local/bin/ \
    && curl -sL https://github.com/projectdiscovery/httpx/releases/latest/download/httpx_linux_amd64.tar.gz | tar xz -C /usr/local/bin/ \
    && curl -sL https://github.com/projectdiscovery/subfinder/releases/latest/download/subfinder_linux_amd64.tar.gz | tar xz -C /usr/local/bin/

WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy wordlists
COPY wordlists/ /wordlists/

# Copy application
COPY xero_scanner/ ./xero_scanner/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/ready', timeout=3).read()\"

CMD [\"uvicorn\", \"xero_scanner.main:app\", \"--host\", \"0.0.0.0\", \"--port\", \"8000\"]
`

## Wordlist Configuration

Wordlists are bundled in /wordlists/ with the following structure:
`
/wordlists/
+-- common-directories.txt      # ~1k common paths
+-- medium-directories.txt      # ~10k paths (optional download)
+-- large-directories.txt       # ~50k paths (optional download)
+-- common-extensions.txt
+-- subdomain-common.txt        # ~500 common subdomains
+-- subdomain-large.txt         # ~10k subdomains (optional download)
+-- api-endpoints.txt
+-- user-agents.txt
+-- default-credentials.txt
`

Scanners can specify wordlist path in args:
`python
{
    \"wordlist\": \"common\",  # Uses /wordlists/common-directories.txt
    \"wordlist_path\": \"/wordlists/custom.txt\",  # Custom path
    \"wordlist_download\": \"https://example.com/wordlist.txt\"  # Download before scan
}
`

---

*End of Document*
