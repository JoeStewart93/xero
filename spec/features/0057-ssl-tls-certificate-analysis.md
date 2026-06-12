# F0057: SSL/TLS Certificate Analysis

## Metadata
| Field | Value |
|---|---|
| ID | F0057 |
| Priority | P0 |
| Status | Planned |
| MVP Phase | 3 |
| Depends on | F0023, F0069 |

## Summary
Deep SSL/TLS certificate inspection and vulnerability detection. Provides certificate chain validation, expiry tracking, SSL Labs-style security rating, weak cipher detection, and vulnerability checks (Heartbleed, POODLE, BEAST).

## Requirements
- Certificate chain validation
- Expiry tracking with alerts
- SSL Labs-style security rating (A-F)
- Weak cipher detection
- Protocol version analysis
- Vulnerability checks (Heartbleed, POODLE, BEAST, etc.)
- Self-signed certificate identification
- Support for scanner service and beacon execution

## Module Arguments

`python
{
    \"targets\": [\"192.168.1.100:443\", \"example.com:443\"],
    \"checks\": [\"certificate\", \"vulnerabilities\", \"ciphers\", \"protocols\"],
    \"sni\": \"example.com\",  // Optional SNI hostname
    \"follow_redirects\": false,
    \"execution_target\": \"auto\"
}
`

## SSL Labs Grade Criteria

| Grade | Criteria |
| :--- | :--- |
| A+ | TLS 1.3, strong ciphers, no vulnerabilities |
| A | TLS 1.2+, strong ciphers, no major vulnerabilities |
| B | TLS 1.2+, some weak ciphers |
| C | TLS 1.0/1.1, or weak ciphers |
| D | Known vulnerabilities |
| F | Critical vulnerabilities or connection failure |

## Result Schema

`json
{
    \"target\": \"192.168.1.100:443\",
    \"scan_time\": \"2024-01-15T10:30:00Z\",
    \"certificate\": {
        \"subject\": {
            \"CN\": \"example.com\",
            \"O\": \"Example Corp\",
            \"OU\": \"IT Department\",
            \"L\": \"New York\",
            \"ST\": \"NY\",
            \"C\": \"US\"
        },
        \"issuer\": {
            \"CN\": \"DigiCert SHA2 Extended Validation Server CA\",
            \"O\": \"DigiCert Inc\",
            \"C\": \"US\"
        },
        \"valid_from\": \"2024-01-01T00:00:00Z\",
        \"valid_to\": \"2025-01-01T00:00:00Z\",
        \"days_until_expiry\": 365,
        \"serial_number\": \"1234:5678:9ABC:DEF0\",
        \"signature_algorithm\": \"sha256WithRSAEncryption\",
        \"key_size\": 2048,
        \"key_type\": \"RSA\",
        \"version\": 3,
        \"san\": [
            \"DNS:example.com\",
            \"DNS:www.example.com\",
            \"DNS:mail.example.com\"
        ],
        \"self_signed\": false,
        \"chain_valid\": true,
        \"chain_length\": 3,
        \"chain\": [
            {
                \"subject\": \"CN=example.com\",
                \"issuer\": \"CN=DigiCert SHA2 EV Server CA\",
                \"valid_from\": \"2024-01-01\",
                \"valid_to\": \"2025-01-01\"
            },
            {
                \"subject\": \"CN=DigiCert SHA2 EV Server CA\",
                \"issuer\": \"CN=DigiCert EV Root CA\",
                \"valid_from\": \"2013-05-06\",
                \"valid_to\": \"2028-05-06\"
            }
        ],
        \"fingerprint_sha1\": \"AA:BB:CC:DD:EE:FF...\",
        \"fingerprint_sha256\": \"11:22:33:44:55:66...\"
    },
    \"vulnerabilities\": {
        \"heartbleed\": {
            \"vulnerable\": false,
            \"description\": \"OpenSSL Heartbleed (CVE-2014-0160)\"
        },
        \"poodle_ssl\": {
            \"vulnerable\": false,
            \"description\": \"POODLE attack on SSL 3.0 (CVE-2014-3566)\"
        },
        \"poodle_tls\": {
            \"vulnerable\": false,
            \"description\": \"POODLE attack on TLS\"
        },
        \"beast\": {
            \"vulnerable\": false,
            \"description\": \"BEAST attack (CVE-2011-3389)\"
        },
        \"freak\": {
            \"vulnerable\": false,
            \"description\": \"FREAK attack (CVE-2015-0204)\"
        },
        \"logjam\": {
            \"vulnerable\": false,
            \"description\": \"Logjam attack (CVE-2015-4000)\"
        },
        \"crime\": {
            \"vulnerable\": false,
            \"description\": \"CRIME attack (CVE-2012-4929)\"
        },
        \"breach\": {
            \"vulnerable\": false,
            \"description\": \"BREACH attack\"
        },
        \"sweet32\": {
            \"vulnerable\": false,
            \"description\": \"SWEET32 attack (CVE-2016-2183)\"
        }
    },
    \"protocols\": {
        \"ssl_2_0\": false,
        \"ssl_3_0\": false,
        \"tls_1_0\": false,
        \"tls_1_1\": false,
        \"tls_1_2\": true,
        \"tls_1_3\": true,
        \"dtls_1_0\": false,
        \"dtls_1_2\": false
    },
    \"ciphers\": [
        {
            \"name\": \"TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384\",
            \"protocol\": \"TLSv1.2\",
            \"key_exchange\": \"ECDHE\",
            \"authentication\": \"RSA\",
            \"encryption\": \"AES_256_GCM\",
            \"mac\": \"AES_GCM\",
            \"strength\": \"strong\",
            \"bits\": 256
        },
        {
            \"name\": \"TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256\",
            \"protocol\": \"TLSv1.2\",
            \"key_exchange\": \"ECDHE\",
            \"authentication\": \"RSA\",
            \"encryption\": \"AES_128_GCM\",
            \"mac\": \"AES_GCM\",
            \"strength\": \"strong\",
            \"bits\": 128
        },
        {
            \"name\": \"TLS_RSA_WITH_RC4_128_SHA\",
            \"protocol\": \"TLSv1.2\",
            \"key_exchange\": \"RSA\",
            \"authentication\": \"RSA\",
            \"encryption\": \"RC4_128\",
            \"mac\": \"SHA\",
            \"strength\": \"weak\",
            \"bits\": 128,
            \"issues\": [\"RC4 is considered weak\"]
        }
    ],
    \"curves\": [
        \"X25519\",
        \"secp384r1\",
        \"secp256r1\"
    ],
    \"ocsp\": {
        \"stapling\": true,
        \"response\": \"good\",
        \"produced_at\": \"2024-01-15T10:00:00Z\",
        \"this_update\": \"2024-01-15T09:00:00Z\",
        \"next_update\": \"2024-01-22T09:00:00Z\"
    },
    \"hsts\": {
        \"present\": true,
        \"max_age\": 31536000,
        \"include_subdomains\": true,
        \"preload\": true
    },
    \"grade\": \"A-\",
    \"issues\": [
        {
            \"severity\": \"medium\",
            \"message\": \"Weak cipher suite detected: TLS_RSA_WITH_RC4_128_SHA\",
            \"recommendation\": \"Disable RC4 cipher suites\"
        }
    ],
    \"summary\": {
        \"total_ciphers\": 12,
        \"strong_ciphers\": 10,
        \"weak_ciphers\": 2,
        \"vulnerabilities_found\": 0,
        \"protocols_supported\": 2
    }
}
`

## Stages

### Stage 1: SSL Analysis Module Backend
**Goal:** Register ssl_analysis module with schema.
**Acceptance Criteria:**
- [ ] Module registered as uiltin.recon.ssl_analysis
- [ ] Args validation for targets, checks
- [ ] cryptography library integration
- [ ] Module metadata exposed in /api/v1/modules

### Stage 2: Certificate Extraction
**Goal:** Extract and parse certificates.
**Acceptance Criteria:**
- [ ] TLS handshake and certificate retrieval
- [ ] Certificate chain extraction
- [ ] Subject/issuer parsing
- [ ] SAN extraction
- [ ] Fingerprint calculation

### Stage 3: Vulnerability Detection
**Goal:** Test for SSL/TLS vulnerabilities.
**Acceptance Criteria:**
- [ ] Heartbleed test
- [ ] POODLE test (SSL 3.0 and TLS)
- [ ] BEAST test
- [ ] FREAK/Logjam tests
- [ ] CRIME/BREACH tests

### Stage 4: Cipher & Protocol Analysis
**Goal:** Analyze supported ciphers and protocols.
**Acceptance Criteria:**
- [ ] Protocol version detection
- [ ] Cipher suite enumeration
- [ ] Strength assessment
- [ ] Curve analysis

### Stage 5: Grading System
**Goal:** Calculate SSL Labs-style grade.
**Acceptance Criteria:**
- [ ] Grade calculation algorithm
- [ ] Issue identification
- [ ] Recommendations generation
- [ ] Summary statistics

## Feature Acceptance Criteria

- [ ] Certificate chain validated
- [ ] Expiry tracked with alerts
- [ ] Vulnerability checks accurate
- [ ] SSL Labs-style grade assigned
- [ ] Weak ciphers identified
- [ ] Works from scanner service and beacon

## Test Plan

### Unit Tests
- [ ] test_ssl_args_validation
- [ ] test_certificate_parsing
- [ ] test_chain_validation
- [ ] test_fingerprint_calculation
- [ ] test_grade_calculation
- [ ] test_vulnerability_detection

### System / Integration Tests
- [ ] Certificate extracted from HTTPS server
- [ ] Chain validation works for valid certs
- [ ] Heartbleed test accurate
- [ ] POODLE test accurate
- [ ] Cipher enumeration complete
- [ ] Grade calculation correct
- [ ] Expiry alerts trigger appropriately

### Playwright Tests
- [ ] SSL Analysis module visible in Recon module browser
- [ ] Submit scan task with valid target
- [ ] Results show certificate details
- [ ] Vulnerabilities displayed with status
- [ ] Grade shown prominently
- [ ] Issues listed with recommendations

## SSL Analysis Implementation

`python
import ssl
import socket
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.x509.oid import NameOID

def analyze_ssl_target(target: str, sni: str = None) -> dict:
    \"\"\"Analyze SSL/TLS configuration of target.\"\"\"

    if \":\" in target:
        host, port = target.rsplit(\":\", 1)
        port = int(port)
    else:
        host = target
        port = 443

    results = {
        \"target\": f\"{host}:{port}\",
        \"certificate\": None,
        \"vulnerabilities\": {},
        \"protocols\": {},
        \"ciphers\": [],
        \"grade\": \"F\",
        \"issues\": [],
    }

    try:
        # Create SSL context
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        # Connect and get certificate
        with socket.create_connection((host, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=sni or host) as ssock:
                # Get certificate
                cert_der = ssock.getpeercert(binary_form=True)
                cert = x509.load_pem_x509_certificate(cert_der, default_backend())

                results[\"certificate\"] = parse_certificate(cert)
                results[\"ciphers\"] = analyze_cipher(ssock.cipher())
                results[\"protocols\"][ssock.version()] = True

    except Exception as e:
        results[\"error\"] = str(e)

    # Test vulnerabilities
    results[\"vulnerabilities\"] = test_vulnerabilities(host, port)

    # Calculate grade
    results[\"grade\"], results[\"issues\"] = calculate_grade(results)

    return results

def parse_certificate(cert: x509.Certificate) -> dict:
    \"\"\"Parse X.509 certificate.\"\"\"
    subject = cert.subject
    issuer = cert.issuer

    return {
        \"subject\": {
            \"CN\": get_attr(subject, NameOID.COMMON_NAME),
            \"O\": get_attr(subject, NameOID.ORGANIZATION_NAME),
            \"OU\": get_attr(subject, NameOID.ORGANIZATIONAL_UNIT_NAME),
            \"L\": get_attr(subject, NameOID.LOCALITY_NAME),
            \"ST\": get_attr(subject, NameOID.STATE_OR_PROVINCE_NAME),
            \"C\": get_attr(subject, NameOID.COUNTRY_NAME),
        },
        \"issuer\": {
            \"CN\": get_attr(issuer, NameOID.COMMON_NAME),
            \"O\": get_attr(issuer, NameOID.ORGANIZATION_NAME),
            \"C\": get_attr(issuer, NameOID.COUNTRY_NAME),
        },
        \"valid_from\": cert.not_valid_before_utc.isoformat(),
        \"valid_to\": cert.not_valid_after_utc.isoformat(),
        \"days_until_expiry\": (cert.not_valid_after_utc - datetime.now(timezone.utc)).days,
        \"serial_number\": hex(cert.serial_number)[2:].upper(),
        \"signature_algorithm\": cert.signature_algorithm_oid._name,
        \"key_size\": cert.public_key.key_size,
        \"key_type\": type(cert.public_key).__name__,
        \"version\": cert.version.value,
        \"san\": extract_san(cert),
        \"self_signed\": subject == issuer,
        \"fingerprint_sha1\": cert.fingerprint(hashes.SHA1()).hex(),
        \"fingerprint_sha256\": cert.fingerprint(hashes.SHA256()).hex(),
    }

def get_attr(name, oid) -> str | None:
    \"\"\"Get attribute from X.509 name.\"\"\"
    try:
        return name.get_attributes_for_oid(oid)[0].value
    except (IndexError, KeyError):
        return None

def extract_san(cert: x509.Certificate) -> list[str]:
    \"\"\"Extract Subject Alternative Names.\"\"\"
    san = []
    try:
        ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        for name in ext.value:
            san.append(f\"{type(name).__name__}:{name.value}\")
    except x509.ExtensionNotFound:
        pass
    return san

def test_vulnerabilities(host: str, port: int) -> dict:
    \"\"\"Test for common SSL/TLS vulnerabilities.\"\"\"
    vulns = {}

    # Heartbleed test
    vulns[\"heartbleed\"] = {
        \"vulnerable\": test_heartbleed(host, port),
        \"description\": \"OpenSSL Heartbleed (CVE-2014-0160)\",
    }

    # POODLE test (SSL 3.0)
    vulns[\"poodle_ssl\"] = {
        \"vulnerable\": test_poodle_ssl(host, port),
        \"description\": \"POODLE attack on SSL 3.0 (CVE-2014-3566)\",
    }

    # BEAST test
    vulns[\"beast\"] = {
        \"vulnerable\": test_beast(host, port),
        \"description\": \"BEAST attack (CVE-2011-3389)\",
    }

    # Add more vulnerability tests...

    return vulns

def calculate_grade(results: dict) -> tuple[str, list[dict]]:
    \"\"\"Calculate SSL Labs-style grade.\"\"\"
    score = 100
    issues = []

    # Deduct for vulnerabilities
    for vuln_name, vuln_data in results.get(\"vulnerabilities\", {}).items():
        if vuln_data.get(\"vulnerable\"):
            score -= 20
            issues.append({
                \"severity\": \"high\",
                \"message\": f\"Vulnerable to {vuln_name}\",
                \"recommendation\": f\"Patch or disable {vuln_name}\",
            })

    # Deduct for weak ciphers
    for cipher in results.get(\"ciphers\", []):
        if cipher.get(\"strength\") == \"weak\":
            score -= 5
            issues.append({
                \"severity\": \"medium\",
                \"message\": f\"Weak cipher: {cipher['name']}\",
                \"recommendation\": \"Disable weak cipher suites\",
            })

    # Deduct for old protocols
    if results.get(\"protocols\", {}).get(\"SSLv3\"):
        score -= 10
        issues.append({
            \"severity\": \"high\",
            \"message\": \"SSL 3.0 enabled\",
            \"recommendation\": \"Disable SSL 3.0\",
        })

    # Calculate grade
    if score >= 90:
        grade = \"A\"
    elif score >= 75:
        grade = \"B\"
    elif score >= 60:
        grade = \"C\"
    elif score >= 40:
        grade = \"D\"
    else:
        grade = \"F\"

    return grade, issues
`

---

*End of Document*
