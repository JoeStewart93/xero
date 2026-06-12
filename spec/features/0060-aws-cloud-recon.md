# F0060: AWS Cloud Recon

## Metadata
| Field | Value |
|---|---|
| ID | F0060 |
| Priority | P1 |
| Status | Planned |
| MVP Phase | 4 |
| Depends on | F0016, F0030, F0069 |

## Summary
AWS cloud infrastructure discovery and enumeration. Supports public S3 bucket enumeration, authenticated scans with credentials, EC2 instance metadata discovery, and IAM policy analysis.

## Requirements
- S3 bucket enumeration (public and authenticated)
- S3 bucket policy analysis
- EC2 instance metadata (if creds available)
- IAM policy analysis (if creds available)
- RDS instance discovery
- Support for scanner service and beacon execution

## Module Arguments

`python
{
    \"targets\": [\"arn:aws:s3:::bucket-name\", \"example.s3.amazonaws.com\"],
    \"creds\": {  // Optional for public enum
        \"access_key\": \"AKIA...\",
        \"secret_key\": \"...\",
        \"session_token\": \"...\",  // Optional for STS
        \"region\": \"us-east-1\"
    },
    \"enum_types\": [\"s3_buckets\", \"ec2_instances\", \"iam_policies\", \"rds_instances\"],
    \"execution_target\": \"auto\"
}
`

## Result Schema

`json
{
    \"provider\": \"aws\",
    \"scan_time\": \"2024-01-15T10:30:00Z\",
    \"s3_buckets\": [
        {
            \"name\": \"example-bucket\",
            \"arn\": \"arn:aws:s3:::example-bucket\",
            \"region\": \"us-east-1\",
            \"public\": true,
            \"read_access\": true,
            \"write_access\": false,
            \"delete_access\": false,
            \"policy\": {
                \"public_read\": true,
                \"public_write\": false,
                \"cross_account\": false
            },
            \"objects_sample\": [
                {\"key\": \"index.html\", \"size\": 1234, \"last_modified\": \"2024-01-01\"},
                {\"key\": \"config.json\", \"size\": 567, \"last_modified\": \"2024-01-02\"}
            ],
            \"object_count\": 150,
            \"size_bytes\": 1048576
        }
    ],
    \"ec2_instances\": [
        {
            \"instance_id\": \"i-1234567890abcdef0\",
            \"instance_type\": \"t3.micro\",
            \"state\": \"running\",
            \"public_ip\": \"54.123.45.67\",
            \"private_ip\": \"10.0.1.100\",
            \"ami_id\": \"ami-0c55b159cbfafe1f0\",
            \"launch_time\": \"2024-01-01T00:00:00Z\",
            \"tags\": {\"Name\": \"WebServer\", \"Environment\": \"Production\"}
        }
    ],
    \"iam_findings\": [
        {
            \"type\": \"root_user\",
            \"severity\": \"medium\",
            \"description\": \"Root user has access keys configured\",
            \"recommendation\": \"Use IAM users for API access\"
        },
        {
            \"type\": \"overly_permissive_policy\",
            \"severity\": \"high\",
            \"description\": \"Policy allows *:* on all resources\",
            \"policy_arn\": \"arn:aws:iam::123456789012:policy/AdminAccess\"
        }
    ],
    \"summary\": {
        \"total_buckets\": 5,
        \"public_buckets\": 2,
        \"total_instances\": 3,
        \"iam_findings\": 2
    }
}
`

## Feature Acceptance Criteria

- [ ] Public S3 bucket enumeration works without credentials
- [ ] Authenticated scans use provided credentials
- [ ] S3 bucket policies analyzed for public access
- [ ] EC2 instances discovered with credentials
- [ ] IAM findings identified
- [ ] Results create cloud assets

## Test Plan

### Unit Tests
- [ ] test_aws_args_validation
- [ ] test_s3_bucket_name_validation
- [ ] test_aws_creds_validation
- [ ] test_bucket_policy_parsing

### System / Integration Tests
- [ ] Public S3 bucket discovered
- [ ] Authenticated S3 scan works
- [ ] EC2 instances listed with credentials
- [ ] IAM findings generated
- [ ] Results create cloud assets

### Playwright Tests
- [ ] AWS Recon module visible in Recon module browser
- [ ] Credential input fields available
- [ ] Submit scan with valid target
- [ ] Results show S3 buckets
- [ ] Public buckets highlighted

---

*End of Document*
