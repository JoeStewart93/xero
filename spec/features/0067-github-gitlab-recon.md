# F0067: GitHub/GitLab Recon

## Metadata
| Field | Value |
|---|---|
| ID | F0067 |
| Priority | P1 |
| Status | Planned |
| MVP Phase | 4 |
| Depends on | F0016, F0069 |

## Summary
GitHub and GitLab organization enumeration. Discovers repositories, detects secrets/tokens in code, and finds infrastructure-as-code configurations.

## Requirements
- Organization repository enumeration
- Secret/token leakage scanning
- Infrastructure-as-code discovery
- Public and authenticated scans

## Module Arguments

`python
{
    \"targets\": [\"github.com/example-org\", \"gitlab.example.com\"],
    \"platform\": \"github\",  // github, gitlab
    \"token\": \"ghp_...\",  // Optional for private repos
    \"enum_types\": [\"repositories\", \"secrets\", \"iac\"],
    \"execution_target\": \"auto\"
}
`

## Result Schema

`json
{
    \"platform\": \"github\",
    \"organization\": \"example-org\",
    \"repositories\": [
        {\"name\": \"web-app\", \"private\": false, \"language\": \"JavaScript\", \"stars\": 150},
        {\"name\": \"infrastructure\", \"private\": false, \"language\": \"HCL\", \"stars\": 10}
    ],
    \"secrets_found\": [
        {
            \"repository\": \"web-app\",
            \"file\": \"config.js\",
            \"line\": 15,
            \"type\": \"AWS Access Key\",
            \"value\": \"AKIA...\"
        }
    ],
    \"iac_files\": [
        {
            \"repository\": \"infrastructure\",
            \"file\": \"main.tf\",
            \"type\": \"Terraform\",
            \"resources\": [\"aws_instance\", \"aws_s3_bucket\"]
        }
    ]
}
`

## Feature Acceptance Criteria

- [ ] Repositories enumerated for organization
- [ ] Secrets detected in code
- [ ] IaC files identified
- [ ] Results create code assets

---

*End of Document*
