<#
.SYNOPSIS
Removes smoke data created by scripts/smoke-data.ps1.

.EXAMPLE
.\scripts\clean-smoke-data.ps1

.EXAMPLE
.\scripts\clean-smoke-data.ps1 -ResetVolumes
#>
[CmdletBinding()]
param(
    [string]$Prefix = "xero-smoke",
    [switch]$ResetVolumes,
    [switch]$IncludeScaffolds,
    [switch]$PruneEmptyAutoGroups,
    [string]$C2ComposeFile = "docker-compose.c2.yml"
)

$ErrorActionPreference = "Stop"

if ($Prefix -notmatch '^[A-Za-z0-9._-]+$') {
    throw "Prefix may only contain letters, numbers, dot, underscore, and dash."
}

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$PlatformDir = Join-Path $RepoRoot "platform"

function Invoke-Compose {
    param(
        [string]$ComposeFile,
        [string[]]$Arguments
    )
    Push-Location $PlatformDir
    try {
        & docker compose -f $ComposeFile @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "docker compose -f $ComposeFile $($Arguments -join ' ') failed with exit code $LASTEXITCODE."
        }
    }
    finally {
        Pop-Location
    }
}

if ($ResetVolumes) {
    if ($IncludeScaffolds) {
        Invoke-Compose "docker-compose.scanner.yml" @("down", "-v")
        Invoke-Compose "docker-compose.handler.yml" @("down", "-v")
    }
    Invoke-Compose "docker-compose.c2.yml" @("down", "-v")
    Invoke-Compose "docker-compose.bff.yml" @("down", "-v")
    Write-Host "Removed local compose containers and volumes."
    return
}

$pruneSql = ""
if ($PruneEmptyAutoGroups) {
    $pruneSql = @"
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
"@
}

$prefixLike = "$Prefix%"
$prefixContains = "%$Prefix%"
$sql = @"
BEGIN;

CREATE TEMP TABLE smoke_beacons ON COMMIT DROP AS
SELECT id
FROM beacons
WHERE machine_fingerprint_hash LIKE '$prefixLike'
   OR hostname LIKE '$prefixLike';

CREATE TEMP TABLE smoke_workers ON COMMIT DROP AS
SELECT id
FROM infrastructure_workers
WHERE name LIKE '$prefixLike';

CREATE TEMP TABLE smoke_profiles ON COMMIT DROP AS
SELECT id
FROM traffic_profiles
WHERE name LIKE '$prefixLike';

CREATE TEMP TABLE smoke_tasks ON COMMIT DROP AS
SELECT id
FROM tasks
WHERE beacon_id IN (SELECT id FROM smoke_beacons)
   OR args::text LIKE '$prefixContains';

CREATE TEMP TABLE smoke_task_results ON COMMIT DROP AS
SELECT id
FROM task_results
WHERE task_id IN (SELECT id FROM smoke_tasks)
   OR beacon_id IN (SELECT id FROM smoke_beacons);

CREATE TEMP TABLE smoke_sessions ON COMMIT DROP AS
SELECT id
FROM sessions
WHERE beacon_id IN (SELECT id FROM smoke_beacons)
   OR actor_subject LIKE '$prefixLike';

CREATE TEMP TABLE smoke_file_transfers ON COMMIT DROP AS
SELECT id
FROM file_transfers
WHERE beacon_id IN (SELECT id FROM smoke_beacons)
   OR session_id IN (SELECT id FROM smoke_sessions)
   OR remote_path LIKE '$prefixContains'
   OR filename LIKE '$prefixLike';

CREATE TEMP TABLE smoke_scan_jobs ON COMMIT DROP AS
SELECT id
FROM scan_jobs
WHERE args::text LIKE '$prefixContains'
   OR actor_subject LIKE '$prefixLike';

CREATE TEMP TABLE smoke_assets ON COMMIT DROP AS
SELECT DISTINCT asset_id AS id
FROM asset_beacon_links
WHERE beacon_id IN (SELECT id FROM smoke_beacons)
UNION
SELECT id
FROM assets
WHERE dedup_key LIKE 'beacon:$prefixLike'
   OR display_name LIKE '$prefixLike'
   OR hostname LIKE '$prefixLike'
   OR metadata::text LIKE '$prefixContains';

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

WITH deleted AS (DELETE FROM protocol_security_events WHERE beacon_id IN (SELECT id FROM smoke_beacons) OR message LIKE '$prefixContains' RETURNING 1)
SELECT 'protocol_security_events' AS table_name, count(*) AS deleted FROM deleted;

WITH deleted AS (DELETE FROM worker_pairing_tokens WHERE worker_id IN (SELECT id FROM smoke_workers) OR name LIKE '$prefixLike' RETURNING 1)
SELECT 'worker_pairing_tokens' AS table_name, count(*) AS deleted FROM deleted;

WITH deleted AS (DELETE FROM worker_events WHERE worker_id IN (SELECT id FROM smoke_workers) OR message LIKE '$prefixContains' RETURNING 1)
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

$pruneSql

COMMIT;
"@

Push-Location $PlatformDir
try {
    $sql | & docker compose -f $C2ComposeFile exec -T c2-postgres sh -lc 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
    if ($LASTEXITCODE -ne 0) {
        throw "Smoke data cleanup failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}

Write-Host "Removed smoke data with prefix '$Prefix'."
