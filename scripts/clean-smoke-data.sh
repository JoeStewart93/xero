#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
PLATFORM_DIR="${REPO_ROOT}/platform"
PREFIX="xero-smoke"
RESET_VOLUMES=0
INCLUDE_SCAFFOLDS=0
PRUNE_EMPTY_AUTO_GROUPS=0
C2_COMPOSE_FILE="docker-compose.c2.yml"

usage() {
  cat <<'USAGE'
Usage: scripts/clean-smoke-data.sh [options]

Options:
  --prefix prefix             Smoke data prefix. Default: xero-smoke.
  --reset-volumes             Stop compose stacks and remove all local volumes.
  --include-scaffolds         Include handler/scanner stacks when resetting volumes.
  --prune-empty-auto-groups   Remove empty automatic asset groups after smoke cleanup.
  --c2-compose-file file      C2 compose file. Default: docker-compose.c2.yml.
  -h, --help                  Show this help.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prefix) PREFIX="$2"; shift ;;
    --reset-volumes) RESET_VOLUMES=1 ;;
    --include-scaffolds) INCLUDE_SCAFFOLDS=1 ;;
    --prune-empty-auto-groups) PRUNE_EMPTY_AUTO_GROUPS=1 ;;
    --c2-compose-file) C2_COMPOSE_FILE="$2"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
  esac
  shift
done

[[ "${PREFIX}" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "Prefix may only contain letters, numbers, dot, underscore, and dash." >&2; exit 2; }
command -v docker >/dev/null 2>&1 || { echo "docker is required on PATH." >&2; exit 1; }

compose() {
  local compose_file="$1"
  shift
  (cd "${PLATFORM_DIR}" && docker compose -f "${compose_file}" "$@")
}

if [[ "${RESET_VOLUMES}" -eq 1 ]]; then
  if [[ "${INCLUDE_SCAFFOLDS}" -eq 1 ]]; then
    compose docker-compose.scanner.yml down -v
    compose docker-compose.handler.yml down -v
  fi
  compose docker-compose.c2.yml down -v
  compose docker-compose.bff.yml down -v
  echo "Removed local compose containers and volumes."
  exit 0
fi

PREFIX_LIKE="${PREFIX}%"
PREFIX_CONTAINS="%${PREFIX}%"

if [[ "${PRUNE_EMPTY_AUTO_GROUPS}" -eq 1 ]]; then
  PRUNE_SQL=$(cat <<'SQL'
WITH empty_auto_groups AS (
  SELECT g.id
  FROM asset_groups g
  WHERE g.type = 'auto'
    AND NOT EXISTS (SELECT 1 FROM asset_group_memberships m WHERE m.group_id = g.id)
),
deleted_group_events AS (
  DELETE FROM asset_grouping_events
  WHERE group_id IN (SELECT id FROM empty_auto_groups)
  RETURNING 1
),
deleted_groups AS (
  DELETE FROM asset_groups
  WHERE id IN (SELECT id FROM empty_auto_groups)
  RETURNING 1
)
SELECT 'empty_auto_groups' AS table_name, count(*) AS deleted FROM deleted_groups;
SQL
)
else
  PRUNE_SQL=""
fi

compose "${C2_COMPOSE_FILE}" exec -T c2-postgres sh -lc 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<SQL
BEGIN;

CREATE TEMP TABLE smoke_beacons ON COMMIT DROP AS
SELECT id
FROM beacons
WHERE machine_fingerprint_hash LIKE '${PREFIX_LIKE}'
   OR hostname LIKE '${PREFIX_LIKE}';

CREATE TEMP TABLE smoke_workers ON COMMIT DROP AS
SELECT id
FROM infrastructure_workers
WHERE name LIKE '${PREFIX_LIKE}';

CREATE TEMP TABLE smoke_profiles ON COMMIT DROP AS
SELECT id
FROM traffic_profiles
WHERE name LIKE '${PREFIX_LIKE}';

CREATE TEMP TABLE smoke_tasks ON COMMIT DROP AS
SELECT id
FROM tasks
WHERE beacon_id IN (SELECT id FROM smoke_beacons)
   OR args::text LIKE '${PREFIX_CONTAINS}';

CREATE TEMP TABLE smoke_task_results ON COMMIT DROP AS
SELECT id
FROM task_results
WHERE task_id IN (SELECT id FROM smoke_tasks)
   OR beacon_id IN (SELECT id FROM smoke_beacons);

CREATE TEMP TABLE smoke_sessions ON COMMIT DROP AS
SELECT id
FROM sessions
WHERE beacon_id IN (SELECT id FROM smoke_beacons)
   OR actor_subject LIKE '${PREFIX_LIKE}';

CREATE TEMP TABLE smoke_file_transfers ON COMMIT DROP AS
SELECT id
FROM file_transfers
WHERE beacon_id IN (SELECT id FROM smoke_beacons)
   OR session_id IN (SELECT id FROM smoke_sessions)
   OR remote_path LIKE '${PREFIX_CONTAINS}'
   OR filename LIKE '${PREFIX_LIKE}';

CREATE TEMP TABLE smoke_scan_jobs ON COMMIT DROP AS
SELECT id
FROM scan_jobs
WHERE args::text LIKE '${PREFIX_CONTAINS}'
   OR actor_subject LIKE '${PREFIX_LIKE}';

CREATE TEMP TABLE smoke_assets ON COMMIT DROP AS
SELECT DISTINCT asset_id AS id
FROM asset_beacon_links
WHERE beacon_id IN (SELECT id FROM smoke_beacons)
UNION
SELECT id
FROM assets
WHERE dedup_key LIKE 'beacon:${PREFIX_LIKE}'
   OR display_name LIKE '${PREFIX_LIKE}'
   OR hostname LIKE '${PREFIX_LIKE}'
   OR metadata::text LIKE '${PREFIX_CONTAINS}';

CREATE TEMP TABLE smoke_artifacts ON COMMIT DROP AS
SELECT artifact_id AS id
FROM task_result_artifacts
WHERE task_result_id IN (SELECT id FROM smoke_task_results)
UNION
SELECT artifact_id AS id
FROM file_transfers
WHERE id IN (SELECT id FROM smoke_file_transfers)
  AND artifact_id IS NOT NULL;

WITH deleted AS (DELETE FROM scan_result_chunks WHERE scan_job_id IN (SELECT id FROM smoke_scan_jobs) RETURNING 1)
SELECT 'scan_result_chunks' AS table_name, count(*) AS deleted FROM deleted;

WITH deleted AS (DELETE FROM asset_observations WHERE scan_job_id IN (SELECT id FROM smoke_scan_jobs) OR beacon_id IN (SELECT id FROM smoke_beacons) RETURNING 1)
SELECT 'asset_observations' AS table_name, count(*) AS deleted FROM deleted;

WITH deleted AS (DELETE FROM asset_relationships WHERE scan_job_id IN (SELECT id FROM smoke_scan_jobs) OR source_asset_id IN (SELECT id FROM smoke_assets) OR target_asset_id IN (SELECT id FROM smoke_assets) RETURNING 1)
SELECT 'asset_relationships' AS table_name, count(*) AS deleted FROM deleted;

WITH deleted AS (DELETE FROM scan_jobs WHERE id IN (SELECT id FROM smoke_scan_jobs) RETURNING 1)
SELECT 'scan_jobs' AS table_name, count(*) AS deleted FROM deleted;

WITH deleted AS (DELETE FROM file_transfer_chunks WHERE transfer_id IN (SELECT id FROM smoke_file_transfers) RETURNING 1)
SELECT 'file_transfer_chunks' AS table_name, count(*) AS deleted FROM deleted;

WITH deleted AS (DELETE FROM file_transfers WHERE id IN (SELECT id FROM smoke_file_transfers) RETURNING 1)
SELECT 'file_transfers' AS table_name, count(*) AS deleted FROM deleted;

WITH deleted AS (DELETE FROM task_result_artifacts WHERE task_result_id IN (SELECT id FROM smoke_task_results) RETURNING 1)
SELECT 'task_result_artifacts' AS table_name, count(*) AS deleted FROM deleted;

WITH deleted AS (DELETE FROM result_chunks WHERE task_result_id IN (SELECT id FROM smoke_task_results) OR task_id IN (SELECT id FROM smoke_tasks) OR beacon_id IN (SELECT id FROM smoke_beacons) RETURNING 1)
SELECT 'result_chunks' AS table_name, count(*) AS deleted FROM deleted;

WITH deleted AS (DELETE FROM task_results WHERE id IN (SELECT id FROM smoke_task_results) RETURNING 1)
SELECT 'task_results' AS table_name, count(*) AS deleted FROM deleted;

WITH deleted AS (DELETE FROM task_audit_events WHERE task_id IN (SELECT id FROM smoke_tasks) OR beacon_id IN (SELECT id FROM smoke_beacons) RETURNING 1)
SELECT 'task_audit_events' AS table_name, count(*) AS deleted FROM deleted;

WITH deleted AS (DELETE FROM tasks WHERE id IN (SELECT id FROM smoke_tasks) RETURNING 1)
SELECT 'tasks' AS table_name, count(*) AS deleted FROM deleted;

WITH deleted AS (DELETE FROM registry_audit_events WHERE session_id IN (SELECT id FROM smoke_sessions) OR beacon_id IN (SELECT id FROM smoke_beacons) RETURNING 1)
SELECT 'registry_audit_events' AS table_name, count(*) AS deleted FROM deleted;

WITH deleted AS (DELETE FROM registry_confirmations WHERE session_id IN (SELECT id FROM smoke_sessions) OR beacon_id IN (SELECT id FROM smoke_beacons) RETURNING 1)
SELECT 'registry_confirmations' AS table_name, count(*) AS deleted FROM deleted;

WITH deleted AS (DELETE FROM sessions WHERE id IN (SELECT id FROM smoke_sessions) RETURNING 1)
SELECT 'sessions' AS table_name, count(*) AS deleted FROM deleted;

WITH deleted AS (DELETE FROM protocol_frame_receipts WHERE beacon_id IN (SELECT id FROM smoke_beacons) RETURNING 1)
SELECT 'protocol_frame_receipts' AS table_name, count(*) AS deleted FROM deleted;

WITH deleted AS (DELETE FROM protocol_security_events WHERE beacon_id IN (SELECT id FROM smoke_beacons) OR message LIKE '${PREFIX_CONTAINS}' RETURNING 1)
SELECT 'protocol_security_events' AS table_name, count(*) AS deleted FROM deleted;

WITH deleted AS (DELETE FROM worker_pairing_tokens WHERE worker_id IN (SELECT id FROM smoke_workers) OR name LIKE '${PREFIX_LIKE}' RETURNING 1)
SELECT 'worker_pairing_tokens' AS table_name, count(*) AS deleted FROM deleted;

WITH deleted AS (DELETE FROM worker_events WHERE worker_id IN (SELECT id FROM smoke_workers) OR message LIKE '${PREFIX_CONTAINS}' RETURNING 1)
SELECT 'worker_events' AS table_name, count(*) AS deleted FROM deleted;

WITH deleted AS (DELETE FROM infrastructure_workers WHERE id IN (SELECT id FROM smoke_workers) RETURNING 1)
SELECT 'infrastructure_workers' AS table_name, count(*) AS deleted FROM deleted;

UPDATE beacons
SET profile_id = NULL, applied_profile_version = NULL, profile_applied_at = NULL
WHERE profile_id IN (SELECT id FROM smoke_profiles);

WITH deleted AS (DELETE FROM traffic_profile_versions WHERE profile_id IN (SELECT id FROM smoke_profiles) RETURNING 1)
SELECT 'traffic_profile_versions' AS table_name, count(*) AS deleted FROM deleted;

WITH deleted AS (DELETE FROM traffic_profiles WHERE id IN (SELECT id FROM smoke_profiles) RETURNING 1)
SELECT 'traffic_profiles' AS table_name, count(*) AS deleted FROM deleted;

WITH deleted AS (DELETE FROM asset_group_memberships WHERE asset_id IN (SELECT id FROM smoke_assets) RETURNING 1)
SELECT 'asset_group_memberships' AS table_name, count(*) AS deleted FROM deleted;

WITH deleted AS (DELETE FROM asset_grouping_events WHERE asset_id IN (SELECT id FROM smoke_assets) RETURNING 1)
SELECT 'asset_grouping_events' AS table_name, count(*) AS deleted FROM deleted;

WITH deleted AS (DELETE FROM asset_identifiers WHERE asset_id IN (SELECT id FROM smoke_assets) RETURNING 1)
SELECT 'asset_identifiers' AS table_name, count(*) AS deleted FROM deleted;

WITH deleted AS (DELETE FROM asset_beacon_links WHERE asset_id IN (SELECT id FROM smoke_assets) OR beacon_id IN (SELECT id FROM smoke_beacons) RETURNING 1)
SELECT 'asset_beacon_links' AS table_name, count(*) AS deleted FROM deleted;

WITH deleted AS (DELETE FROM assets WHERE id IN (SELECT id FROM smoke_assets) RETURNING 1)
SELECT 'assets' AS table_name, count(*) AS deleted FROM deleted;

WITH deleted AS (DELETE FROM beacon_events WHERE beacon_id IN (SELECT id FROM smoke_beacons) RETURNING 1)
SELECT 'beacon_events' AS table_name, count(*) AS deleted FROM deleted;

WITH deleted AS (DELETE FROM beacons WHERE id IN (SELECT id FROM smoke_beacons) RETURNING 1)
SELECT 'beacons' AS table_name, count(*) AS deleted FROM deleted;

WITH deleted AS (DELETE FROM artifacts WHERE id IN (SELECT id FROM smoke_artifacts) RETURNING 1)
SELECT 'artifacts' AS table_name, count(*) AS deleted FROM deleted;

${PRUNE_SQL}

COMMIT;
SQL

echo "Removed smoke data with prefix '${PREFIX}'."
