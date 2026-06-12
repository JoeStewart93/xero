# F0070: External API Key Management

## Metadata
| Field | Value |
|---|---|
| ID | F0070 |
| Priority | P0 |
| Status | Planned |
| MVP Phase | 3 |
| Depends on | F0004 |

## Summary
Centralized management of external API keys for enrichment services (Shodan, Censys, VirusTotal, SecurityTrails). Keys are stored encrypted in PostgreSQL with environment variable fallback. Platform-level configuration for MVP v1.

## Requirements
- Database model for API key storage
- BCrypt hashing for key encryption
- Environment variable override support
- C2 API endpoints for key management
- Key validation/testing endpoint
- Support for: Shodan, Censys, VirusTotal, SecurityTrails

## Database Schema

`python
class ExternalAPIKey(BaseModel):
    __tablename__ = \"external_api_keys\"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    key_hash: Mapped[str] = mapped_column(String(512), nullable=False)  # BCrypt hashed
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_validated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    validation_status: Mapped[str | None] = mapped_column(String(32), nullable=True)  # valid, invalid, unknown
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
`

## Supported Providers

| Provider | API Endpoint | Validation Endpoint |
| :--- | :--- | :--- |
| shodan | https://api.shodan.io | /shodan/host/8.8.8.8 |
| censys | https://search.censys.io/api | /v1/hosts/8.8.8.8 |
| virustotal | https://www.virustotal.com/api/v3 | /ip_addresses/8.8.8.8 |
| securitytrails | https://api.securitytrails.com | /api/domain/google.com |

## API Endpoints

### List API Keys (Providers Only)
`
GET /api/v1/recon/api-keys
`
Returns list of configured providers without exposing keys:
`json
{
    \"keys\": [
        {
            \"id\": \"uuid\",
            \"provider\": \"shodan\",
            \"label\": \"Primary Shodan Key\",
            \"is_active\": true,
            \"validation_status\": \"valid\",
            \"last_validated\": \"2024-01-15T10:30:00Z\"
        }
    ]
}
`

### Create/Update API Key
`
POST /api/v1/recon/api-keys
`
Request:
`json
{
    \"provider\": \"shodan\",
    \"key\": \"actual_api_key_here\",
    \"label\": \"Primary Shodan Key\"
}
`

### Update API Key
`
PATCH /api/v1/recon/api-keys/{id}
`
Request:
`json
{
    \"key\": \"new_api_key\",  // Optional
    \"label\": \"Updated Label\",  // Optional
    \"is_active\": false  // Optional
}
`

### Delete API Key
`
DELETE /api/v1/recon/api-keys/{id}
`

### Validate API Key
`
GET /api/v1/recon/api-keys/{id}/test
`
Tests the key against the provider API and returns validation result.

## Environment Variable Fallback

Keys can be provided via environment variables (takes precedence over database):
`
SHODAN_API_KEY=abc123...
CENSYS_API_KEY=xyz789...
VIRUSTOTAL_API_KEY=def456...
SECURITYTRAILS_API_KEY=ghi012...
`

## Key Encryption

- Keys hashed using BCrypt with cost factor 12
- Platform secret key stored in environment variable PLATFORM_SECRET_KEY
- Keys never logged or returned in API responses (except validation status)

## Stages

### Stage 1: Database Model & Migration
**Goal:** Create database schema for API keys.
**Acceptance Criteria:**
- [ ] Alembic migration creates external_api_keys table
- [ ] Model includes all required fields
- [ ] Unique constraint on provider
- [ ] Index on provider for fast lookups

### Stage 2: CRUD Operations
**Goal:** Implement create, read, update, delete operations.
**Acceptance Criteria:**
- [ ] POST creates new key with BCrypt hash
- [ ] GET returns provider list without keys
- [ ] PATCH updates existing key
- [ ] DELETE removes key
- [ ] Environment variable override works

### Stage 3: Validation Endpoints
**Goal:** Test keys against provider APIs.
**Acceptance Criteria:**
- [ ] Shodan key validation works
- [ ] Censys key validation works
- [ ] VirusTotal key validation works
- [ ] SecurityTrails key validation works
- [ ] Validation status stored in database

### Stage 4: Integration with Scanner Modules
**Goal:** Scanner modules can retrieve keys.
**Acceptance Criteria:**
- [ ] Key retrieval service implemented
- [ ] Scanner modules can fetch active keys
- [ ] Missing keys return clear error
- [ ] Key rotation without restart supported

## Feature Acceptance Criteria

- [ ] API keys stored encrypted in PostgreSQL
- [ ] Environment variable override supported
- [ ] Key validation endpoint works for all providers
- [ ] Scanner modules can access keys programmatically
- [ ] Keys never exposed in API responses

## Test Plan

### Unit Tests
- [ ] test_api_key_model_creation
- [ ] test_bcrypt_hashing
- [ ] test_environment_variable_override
- [ ] test_provider_unique_constraint
- [ ] test_key_retrieval_service

### System / Integration Tests
- [ ] POST /api/v1/recon/api-keys creates key
- [ ] GET /api/v1/recon/api-keys lists providers
- [ ] PATCH /api/v1/recon/api-keys/{id} updates key
- [ ] DELETE /api/v1/recon/api-keys/{id} removes key
- [ ] GET /api/v1/recon/api-keys/{id}/test validates key
- [ ] Scanner module uses key from database
- [ ] Environment variable takes precedence over database

### Playwright Tests
- [ ] Settings page shows API key configuration (if UI implemented)
- [ ] Key validation shows success/failure status

## Key Retrieval Service

`python
# xero_scanner/services/api_keys.py

class APIKeyService:
    @staticmethod
    async def get_key(provider: str) -> str | None:
        \"\"\"Retrieve API key for provider, checking env vars first.\"\"\"
        # Check environment variable
        env_key = os.getenv(f\"{provider.upper()}_API_KEY\")
        if env_key:
            return env_key

        # Check database
        db_key = await db.get_active_key(provider)
        if db_key:
            return db_key.plain_text  # Decrypt from hash

        return None

    @staticmethod
    async def validate_key(provider: str, key: str) -> bool:
        \"\"\"Test key against provider API.\"\"\"
        validators = {
            \"shodan\": validate_shodan_key,
            \"censys\": validate_censys_key,
            \"virustotal\": validate_virustotal_key,
            \"securitytrails\": validate_securitytrails_key,
        }
        validator = validators.get(provider)
        if validator:
            return await validator(key)
        return False
`

---

*End of Document*
