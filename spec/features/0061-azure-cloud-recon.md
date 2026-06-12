# F0061: Azure Cloud Recon

## Metadata
| Field | Value |
|---|---|
| ID | F0061 |
| Priority | P1 |
| Status | Planned |
| MVP Phase | 4 |
| Depends on | F0016, F0030, F0069 |

## Summary
Azure cloud infrastructure discovery and enumeration. Supports storage account enumeration, Azure AD user/group enumeration, ADFS discovery, and Key Vault enumeration.

## Requirements
- Azure Storage account enumeration
- Azure AD user/group enumeration
- ADFS discovery
- Key Vault enumeration
- Support for scanner service and beacon execution

## Module Arguments

`python
{
    \"targets\": [\"example.blob.core.windows.net\", \"tenant.onmicrosoft.com\"],
    \"creds\": {
        \"client_id\": \"...\",
        \"client_secret\": \"...\",
        \"tenant_id\": \"...\"
    },
    \"enum_types\": [\"storage_accounts\", \"ad_users\", \"ad_groups\", \"key_vaults\"],
    \"execution_target\": \"auto\"
}
`

## Feature Acceptance Criteria

- [ ] Azure storage account enumeration works
- [ ] Azure AD users discovered with credentials
- [ ] ADFS endpoints discovered
- [ ] Key Vaults enumerated
- [ ] Results create cloud assets

---

*End of Document*
