# F0064: JWT Analysis

## Metadata
| Field | Value |
|---|---|
| ID | F0064 |
| Priority | P1 |
| Status | Planned |
| MVP Phase | 4 |
| Depends on | F0053, F0069 |

## Summary
JWT token analysis and validation. Decodes tokens, extracts claims, detects algorithm weaknesses (none, HS256/RS256 confusion), and tests weak secrets.

## Requirements
- JWT token decoding
- Claim extraction
- Algorithm weakness detection
- Weak secret testing
- Support for scanner service and beacon execution

## Module Arguments

`python
{
    \"tokens\": [\"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...\"],
    \"checks\": [\"decode\", \"algorithm\", \"claims\", \"weak_secret\"],
    \"secret_wordlist\": \"common-secrets.txt\",
    \"execution_target\": \"auto\"
}
`

## Result Schema

`json
{
    \"token\": \"eyJhbGci...\",
    \"header\": {
        \"alg\": \"HS256\",
        \"typ\": \"JWT\",
        \"weaknesses\": [\"Algorithm is symmetric (HS256) but may be expected as RS256\"]
    },
    \"payload\": {
        \"sub\": \"1234567890\",
        \"name\": \"John Doe\",
        \"admin\": true,
        \"iat\": 1516239022,
        \"exp\": 1516325422
    },
    \"weaknesses\": [
        {\"type\": \"algorithm_confusion\", \"severity\": \"high\", \"description\": \"HS256 may be accepted where RS256 expected\"},
        {\"type\": \"weak_secret\", \"severity\": \"critical\", \"description\": \"Token signed with weak secret 'secret'\"}
    ],
    \"forged_token\": \"eyJhbGci...\"  // If weakness exploited
}
`

## Feature Acceptance Criteria

- [ ] JWT tokens decoded correctly
- [ ] Claims extracted and displayed
- [ ] Algorithm weaknesses detected
- [ ] Weak secrets identified
- [ ] Token forgery demonstrated when possible

---

*End of Document*
