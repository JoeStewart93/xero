#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
PLATFORM_DIR="${REPO_ROOT}/platform"

SKIP_ENV_COPY=0
NO_BUILD=0
INCLUDE_SCAFFOLDS=0
SEED_SMOKE=0
HEALTH_TIMEOUT_SECONDS=180
FRONTEND_URL="http://localhost:3000"
BFF_URL="http://localhost:8000"
C2_URL="http://localhost:8001"
HANDLER_URL="http://localhost:8002"
SCANNER_URL="http://localhost:8003"

usage() {
  cat <<'USAGE'
Usage: scripts/install-local.sh [options]

Options:
  --skip-env-copy          Do not copy platform/.env.example to platform/.env.
  --no-build               Start existing images without rebuilding.
  --include-scaffolds      Start the optional handler and scanner scaffold stacks.
  --seed-smoke             Seed smoke data after the stacks are healthy.
  --timeout seconds        Health wait timeout per service. Default: 180.
  --frontend-url url       Frontend URL. Default: http://localhost:3000.
  --bff-url url            BFF API URL. Default: http://localhost:8000.
  --c2-url url             C2 API URL. Default: http://localhost:8001.
  --handler-url url        Handler scaffold URL. Default: http://localhost:8002.
  --scanner-url url        Scanner scaffold URL. Default: http://localhost:8003.
  -h, --help               Show this help.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-env-copy) SKIP_ENV_COPY=1 ;;
    --no-build) NO_BUILD=1 ;;
    --include-scaffolds) INCLUDE_SCAFFOLDS=1 ;;
    --seed-smoke) SEED_SMOKE=1 ;;
    --timeout) HEALTH_TIMEOUT_SECONDS="$2"; shift ;;
    --frontend-url) FRONTEND_URL="$2"; shift ;;
    --bff-url) BFF_URL="$2"; shift ;;
    --c2-url) C2_URL="$2"; shift ;;
    --handler-url) HANDLER_URL="$2"; shift ;;
    --scanner-url) SCANNER_URL="$2"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
  esac
  shift
done

command -v docker >/dev/null 2>&1 || { echo "docker is required on PATH." >&2; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "curl is required on PATH." >&2; exit 1; }

if [[ "${SKIP_ENV_COPY}" -eq 0 && ! -f "${PLATFORM_DIR}/.env" && -f "${PLATFORM_DIR}/.env.example" ]]; then
  cp "${PLATFORM_DIR}/.env.example" "${PLATFORM_DIR}/.env"
  echo "Created platform/.env from platform/.env.example."
fi

compose() {
  local compose_file="$1"
  shift
  (cd "${PLATFORM_DIR}" && docker compose -f "${compose_file}" "$@")
}

up_args=(up -d)
if [[ "${NO_BUILD}" -eq 0 ]]; then
  up_args+=(--build)
fi

wait_http_ready() {
  local name="$1"
  local url="$2"
  local deadline=$((SECONDS + HEALTH_TIMEOUT_SECONDS))
  until curl -fsS "${url}" >/dev/null 2>&1; do
    if (( SECONDS >= deadline )); then
      echo "${name} did not become ready before timeout: ${url}" >&2
      exit 1
    fi
    sleep 2
  done
  echo "${name} is ready: ${url}"
}

echo "Starting local UI/BFF stack..."
compose docker-compose.bff.yml "${up_args[@]}"

echo "Starting local C2 backend stack..."
compose docker-compose.c2.yml "${up_args[@]}"

if [[ "${INCLUDE_SCAFFOLDS}" -eq 1 ]]; then
  echo "Starting optional beacon handler scaffold..."
  compose docker-compose.handler.yml "${up_args[@]}"

  echo "Starting optional scanner scaffold..."
  compose docker-compose.scanner.yml "${up_args[@]}"
fi

wait_http_ready "BFF API" "${BFF_URL%/}/ready"
wait_http_ready "C2 API" "${C2_URL%/}/ready"
wait_http_ready "Frontend" "${FRONTEND_URL%/}/login"

if [[ "${INCLUDE_SCAFFOLDS}" -eq 1 ]]; then
  wait_http_ready "Beacon handler" "${HANDLER_URL%/}/ready"
  wait_http_ready "Scanner" "${SCANNER_URL%/}/ready"
fi

if [[ "${SEED_SMOKE}" -eq 1 ]]; then
  "${SCRIPT_DIR}/smoke-data.sh" --c2-url "${C2_URL}"
fi

cat <<READY

Xero is ready.
Frontend: ${FRONTEND_URL}
BFF API:   ${BFF_URL}
C2 API:    ${C2_URL}
READY
