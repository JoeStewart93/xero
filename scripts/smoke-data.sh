#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
C2_URL="http://localhost:8001"
C2_PASSWORD="c2_password"
PREFIX="xero-smoke"
APPEND=0
SKIP_TASKS=0
SKIP_WORKERS=0
RUN_RECON_SCAN=0

usage() {
  cat <<'USAGE'
Usage: scripts/smoke-data.sh [options]

Options:
  --c2-url url             C2 API URL. Default: http://localhost:8001.
  --c2-password password   C2 connection password. Default: c2_password.
  --prefix prefix          Smoke data prefix. Default: xero-smoke.
  --append                 Do not clean existing smoke data first.
  --skip-tasks             Do not queue sample shell tasks.
  --skip-workers           Do not register sample infrastructure workers.
  --run-recon-scan         Queue a tiny loopback Nmap scan job.
  -h, --help               Show this help.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --c2-url) C2_URL="$2"; shift ;;
    --c2-password) C2_PASSWORD="$2"; shift ;;
    --prefix) PREFIX="$2"; shift ;;
    --append) APPEND=1 ;;
    --skip-tasks) SKIP_TASKS=1 ;;
    --skip-workers) SKIP_WORKERS=1 ;;
    --run-recon-scan) RUN_RECON_SCAN=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
  esac
  shift
done

[[ "${PREFIX}" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "Prefix may only contain letters, numbers, dot, underscore, and dash." >&2; exit 2; }
command -v curl >/dev/null 2>&1 || { echo "curl is required on PATH." >&2; exit 1; }

C2_URL="${C2_URL%/}"
API_BASE="${C2_URL}/api/v1"

json_field() {
  local json="$1"
  local field="$2"
  printf '%s' "${json}" | sed -nE "s/.*\"${field}\"[[:space:]]*:[[:space:]]*\"([^\"]+)\".*/\1/p" | head -n 1
}

post_json() {
  local url="$1"
  local body="$2"
  shift 2
  curl -fsS -X POST "${url}" -H 'Content-Type: application/json' "$@" --data "${body}"
}

put_json() {
  local url="$1"
  local body="$2"
  shift 2
  curl -fsS -X PUT "${url}" -H 'Content-Type: application/json' "$@" --data "${body}"
}

if [[ "${APPEND}" -eq 0 ]]; then
  "${SCRIPT_DIR}/clean-smoke-data.sh" --prefix "${PREFIX}"
fi

until curl -fsS "${C2_URL}/ready" >/dev/null 2>&1; do
  echo "Waiting for C2 API at ${C2_URL}/ready..."
  sleep 2
done

connect_response="$(post_json "${API_BASE}/c2/connect" "{\"password\":\"${C2_PASSWORD}\"}")"
access_token="$(json_field "${connect_response}" access_token)"
[[ -n "${access_token}" ]] || { echo "Could not parse C2 access token." >&2; exit 1; }
auth_header=(-H "Authorization: Bearer ${access_token}")

profile_response="$(post_json "${API_BASE}/traffic-profiles" "$(cat <<JSON
{
  "name": "${PREFIX}-traffic-profile",
  "template": "custom",
  "description": "Local smoke profile seeded by scripts/smoke-data.sh.",
  "config": {
    "headers": { "X-Xero-Smoke": "${PREFIX}" },
    "jitter": 0.2,
    "padding": { "min_bytes": 0, "max_bytes": 32 },
    "paths": {
      "register": "/api/v1/beacons/register",
      "heartbeat": "/api/v1/beacons/{beacon_id}/heartbeat",
      "poll": "/api/v1/beacons/{beacon_id}/poll",
      "frame": "/api/v1/beacons/{beacon_id}/frame"
    },
    "sleep_seconds": 45,
    "user_agent": "${PREFIX}-agent/1.0"
  }
}
JSON
)" "${auth_header[@]}")"
profile_id="$(json_field "${profile_response}" id)"

beacon_ids=()
beacon_hosts=("${PREFIX}-win-01" "${PREFIX}-linux-01" "${PREFIX}-laptop-01")
beacon_os=("Windows 11" "Ubuntu 24.04" "macOS 15")
beacon_arch=("x64" "x64" "arm64")
beacon_internal=("10.121.0.10" "10.122.0.20" "10.123.0.30")
beacon_external=("198.51.100.121" "198.51.100.122" "198.51.100.123")
beacon_pid=("4121" "4222" "4333")
beacon_fp=("${PREFIX}-fingerprint-win-01" "${PREFIX}-fingerprint-linux-01" "${PREFIX}-fingerprint-macos-01")

for i in 0 1 2; do
  registration="$(post_json "${API_BASE}/beacons/register" "$(cat <<JSON
{
  "machine_fingerprint_hash": "${beacon_fp[$i]}",
  "hostname": "${beacon_hosts[$i]}",
  "os": "${beacon_os[$i]}",
  "architecture": "${beacon_arch[$i]}",
  "internal_ip": "${beacon_internal[$i]}",
  "external_ip": "${beacon_external[$i]}",
  "pid": ${beacon_pid[$i]}
}
JSON
)")"
  beacon_id="$(json_field "${registration}" beacon_id)"
  beacon_token="$(json_field "${registration}" beacon_token)"
  beacon_ids+=("${beacon_id}")

  post_json "${API_BASE}/beacons/${beacon_id}/heartbeat" "$(cat <<JSON
{
  "hostname": "${beacon_hosts[$i]}",
  "os": "${beacon_os[$i]}",
  "architecture": "${beacon_arch[$i]}",
  "internal_ip": "${beacon_internal[$i]}",
  "external_ip": "${beacon_external[$i]}",
  "pid": ${beacon_pid[$i]}
}
JSON
)" -H "Authorization: Bearer ${beacon_token}" >/dev/null
done

if [[ -n "${profile_id}" && "${#beacon_ids[@]}" -gt 0 ]]; then
  put_json "${API_BASE}/beacons/${beacon_ids[0]}/profile" "{\"profile_id\":\"${profile_id}\"}" "${auth_header[@]}" >/dev/null
fi

if [[ "${SKIP_TASKS}" -eq 0 ]]; then
  for i in "${!beacon_ids[@]}"; do
    post_json "${API_BASE}/tasks" "$(cat <<JSON
{
  "beacon_id": "${beacon_ids[$i]}",
  "module": "shell",
  "priority": "normal",
  "args": {
    "command": "echo ${PREFIX} seeded task for ${beacon_hosts[$i]}",
    "shell_type": "auto",
    "timeout_seconds": 30
  }
}
JSON
)" "${auth_header[@]}" >/dev/null
  done
fi

if [[ "${SKIP_WORKERS}" -eq 0 ]]; then
  for kind in scanner beacon-handler; do
    name="${PREFIX}-${kind}"
    pairing="$(post_json "${API_BASE}/infrastructure/pairing-tokens" "{\"kind\":\"${kind}\",\"name\":\"${name}\"}" "${auth_header[@]}")"
    pairing_token="$(json_field "${pairing}" pairing_token)"
    if [[ "${kind}" == "scanner" ]]; then
      endpoint="http://scanner.local:8000"
      capabilities='["tcp-connect","nmap","service-enumeration"]'
      capacity=8
    else
      endpoint="http://handler.local:8000"
      capabilities='["rest","long-poll","websocket"]'
      capacity=500
    fi
    registration="$(post_json "${API_BASE}/infrastructure/workers/register" "$(cat <<JSON
{
  "kind": "${kind}",
  "name": "${name}",
  "pairing_token": "${pairing_token}",
  "endpoint": "${endpoint}",
  "capabilities": ${capabilities},
  "capacity": ${capacity},
  "current_load": 1,
  "version": "smoke"
}
JSON
)")"
    worker_id="$(json_field "${registration}" worker_id)"
    worker_token="$(json_field "${registration}" worker_token)"
    post_json "${API_BASE}/infrastructure/workers/${worker_id}/heartbeat" "$(cat <<JSON
{
  "endpoint": "${endpoint}",
  "capabilities": ${capabilities},
  "capacity": ${capacity},
  "current_load": 1,
  "version": "smoke"
}
JSON
)" -H "Authorization: Bearer ${worker_token}" >/dev/null
  done
fi

if [[ "${RUN_RECON_SCAN}" -eq 1 ]]; then
  post_json "${API_BASE}/scan-jobs" "$(cat <<'JSON'
{
  "module": "builtin.portscan",
  "args": {
    "targets": ["127.0.0.1"],
    "port_range": "1-1",
    "timeout_ms": 250,
    "max_threads": 4,
    "scan_engine": "nmap",
    "scan_technique": "tcp-connect",
    "timing_template": 3,
    "service_detection": false,
    "os_detection": false,
    "dns_resolution": false,
    "execution_target": "auto"
  }
}
JSON
)" "${auth_header[@]}" >/dev/null
fi

echo "Seeded Xero smoke data with prefix '${PREFIX}'."
echo "Beacons: ${#beacon_ids[@]}"
echo "Traffic profile: ${PREFIX}-traffic-profile"
