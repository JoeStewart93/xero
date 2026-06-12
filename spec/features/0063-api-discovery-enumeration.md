# F0063: API Discovery & Enumeration

## Metadata
| Field | Value |
|---|---|
| ID | F0063 |
| Priority | P1 |
| Status | Planned |
| MVP Phase | 4 |
| Depends on | F0053, F0069 |

## Summary
Modern API endpoint discovery and enumeration. Detects OpenAPI/Swagger specifications, GraphQL endpoints, REST API paths, and API key leakage.

## Requirements
- OpenAPI/Swagger endpoint detection
- GraphQL endpoint discovery
- REST API path enumeration
- API key leakage detection
- Support for scanner service and beacon execution

## Module Arguments

`python
{
    \"target\": \"https://api.example.com\",
    \"enum_types\": [\"openapi\", \"graphql\", \"rest_paths\"],
    \"wordlist\": \"api-common\",
    \"headers\": {\"Authorization\": \"Bearer token\"},
    \"execution_target\": \"auto\"
}
`

## Result Schema

`json
{
    \"target\": \"https://api.example.com\",
    \"openapi\": {
        \"found\": true,
        \"url\": \"https://api.example.com/openapi.json\",
        \"version\": \"3.0.0\",
        \"title\": \"Example API\",
        \"endpoints\": [
            {\"method\": \"GET\", \"path\": \"/v1/users\"},
            {\"method\": \"POST\", \"path\": \"/v1/users\"}
        ]
    },
    \"graphql\": {
        \"found\": true,
        \"url\": \"https://api.example.com/graphql\",
        \"introspection_enabled\": true,
        \"query_count\": 150,
        \"mutation_count\": 50
    },
    \"discovered_paths\": [
        {\"path\": \"/v1/users\", \"methods\": [\"GET\", \"POST\"], \"status\": 200},
        {\"path\": \"/v1/config\", \"methods\": [\"GET\"], \"status\": 200, \"sensitive\": true}
    ],
    \"api_keys_found\": [
        {\"type\": \"AWS\", \"key\": \"AKIA...\", \"location\": \"/v1/config\"}
    ]
}
`

## Feature Acceptance Criteria

- [ ] OpenAPI/Swagger endpoints discovered
- [ ] GraphQL endpoints detected
- [ ] REST API paths enumerated
- [ ] API keys detected in responses
- [ ] Results create API assets

---

*End of Document*
