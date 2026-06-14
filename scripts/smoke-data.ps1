<#
.SYNOPSIS
Seeds deterministic local C2 smoke data for UI and API validation.

.EXAMPLE
.\scripts\smoke-data.ps1
#>
[CmdletBinding()]
param(
    [string]$C2Url = "http://localhost:8001",
    [string]$C2Password = "c2_password",
    [string]$Prefix = "xero-smoke",
    [switch]$Append,
    [switch]$SkipTasks,
    [switch]$SkipWorkers,
    [switch]$RunReconScan
)

$ErrorActionPreference = "Stop"

if ($Prefix -notmatch '^[A-Za-z0-9._-]+$') {
    throw "Prefix may only contain letters, numbers, dot, underscore, and dash."
}

$C2Url = $C2Url.TrimEnd("/")
$ApiBase = "$C2Url/api/v1"

function Invoke-Json {
    param(
        [ValidateSet("GET", "POST", "PUT", "PATCH", "DELETE")]
        [string]$Method,
        [string]$Uri,
        [object]$Body = $null,
        [hashtable]$Headers = @{}
    )

    $args = @{
        Uri = $Uri
        Method = $Method
        Headers = $Headers
    }
    if ($null -ne $Body) {
        $args.ContentType = "application/json"
        $args.Body = ($Body | ConvertTo-Json -Depth 20)
    }
    Invoke-RestMethod @args
}

function Wait-HttpReady {
    param([string]$Url)
    $deadline = (Get-Date).AddSeconds(90)
    while ((Get-Date) -lt $deadline) {
        try {
            Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5 | Out-Null
            return
        }
        catch {
            Start-Sleep -Seconds 2
        }
    }
    throw "C2 API did not become ready: $Url"
}

if (-not $Append) {
    $cleanupScript = Join-Path $PSScriptRoot "clean-smoke-data.ps1"
    & $cleanupScript -Prefix $Prefix
    if ($LASTEXITCODE -ne 0) {
        throw "Smoke cleanup failed before seeding."
    }
}

Wait-HttpReady "$C2Url/ready"

$connect = Invoke-Json -Method POST -Uri "$ApiBase/c2/connect" -Body @{ password = $C2Password }
$c2Headers = @{ Authorization = "Bearer $($connect.access_token)" }

$profile = Invoke-Json -Method POST -Uri "$ApiBase/traffic-profiles" -Headers $c2Headers -Body @{
    name = "$Prefix-traffic-profile"
    template = "custom"
    description = "Local smoke profile seeded by scripts/smoke-data.ps1."
    config = @{
        headers = @{ "X-Xero-Smoke" = $Prefix }
        jitter = 0.2
        padding = @{ min_bytes = 0; max_bytes = 32 }
        paths = @{
            register = "/api/v1/beacons/register"
            heartbeat = "/api/v1/beacons/{beacon_id}/heartbeat"
            poll = "/api/v1/beacons/{beacon_id}/poll"
            frame = "/api/v1/beacons/{beacon_id}/frame"
        }
        sleep_seconds = 45
        user_agent = "$Prefix-agent/1.0"
    }
}

$beaconSpecs = @(
    @{
        hostname = "$Prefix-win-01"; os = "Windows 11"; architecture = "x64";
        internal_ip = "10.121.0.10"; external_ip = "198.51.100.121"; pid = 4121;
        machine_fingerprint_hash = "$Prefix-fingerprint-win-01"
    },
    @{
        hostname = "$Prefix-linux-01"; os = "Ubuntu 24.04"; architecture = "x64";
        internal_ip = "10.122.0.20"; external_ip = "198.51.100.122"; pid = 4222;
        machine_fingerprint_hash = "$Prefix-fingerprint-linux-01"
    },
    @{
        hostname = "$Prefix-laptop-01"; os = "macOS 15"; architecture = "arm64";
        internal_ip = "10.123.0.30"; external_ip = "198.51.100.123"; pid = 4333;
        machine_fingerprint_hash = "$Prefix-fingerprint-macos-01"
    }
)

$seededBeacons = @()
foreach ($spec in $beaconSpecs) {
    $registration = Invoke-Json -Method POST -Uri "$ApiBase/beacons/register" -Body $spec
    $beaconHeaders = @{ Authorization = "Bearer $($registration.beacon_token)" }
    Invoke-Json -Method POST -Uri "$ApiBase/beacons/$($registration.beacon_id)/heartbeat" -Headers $beaconHeaders -Body @{
        hostname = $spec.hostname
        os = $spec.os
        architecture = $spec.architecture
        internal_ip = $spec.internal_ip
        external_ip = $spec.external_ip
        pid = $spec.pid
    } | Out-Null
    $seededBeacons += [pscustomobject]@{
        Id = $registration.beacon_id
        Token = $registration.beacon_token
        Hostname = $spec.hostname
    }
}

if ($seededBeacons.Count -gt 0) {
    Invoke-Json -Method PUT -Uri "$ApiBase/beacons/$($seededBeacons[0].Id)/profile" -Headers $c2Headers -Body @{
        profile_id = $profile.id
    } | Out-Null
}

if (-not $SkipTasks) {
    foreach ($beacon in $seededBeacons) {
        Invoke-Json -Method POST -Uri "$ApiBase/tasks" -Headers $c2Headers -Body @{
            beacon_id = $beacon.Id
            module = "shell"
            priority = "normal"
            args = @{
                command = "echo $Prefix seeded task for $($beacon.Hostname)"
                shell_type = "auto"
                timeout_seconds = 30
            }
        } | Out-Null
    }
}

if (-not $SkipWorkers) {
    foreach ($kind in @("scanner", "beacon-handler")) {
        $name = "$Prefix-$kind"
        $pairing = Invoke-Json -Method POST -Uri "$ApiBase/infrastructure/pairing-tokens" -Headers $c2Headers -Body @{
            kind = $kind
            name = $name
        }
        $registration = Invoke-Json -Method POST -Uri "$ApiBase/infrastructure/workers/register" -Body @{
            kind = $kind
            name = $name
            pairing_token = $pairing.pairing_token
            endpoint = if ($kind -eq "scanner") { "http://scanner.local:8000" } else { "http://handler.local:8000" }
            capabilities = if ($kind -eq "scanner") { @("tcp-connect", "nmap", "service-enumeration") } else { @("rest", "long-poll", "websocket") }
            capacity = if ($kind -eq "scanner") { 8 } else { 500 }
            current_load = 1
            version = "smoke"
        }
        Invoke-Json -Method POST -Uri "$ApiBase/infrastructure/workers/$($registration.worker_id)/heartbeat" -Headers @{
            Authorization = "Bearer $($registration.worker_token)"
        } -Body @{
            endpoint = if ($kind -eq "scanner") { "http://scanner.local:8000" } else { "http://handler.local:8000" }
            capabilities = if ($kind -eq "scanner") { @("tcp-connect", "nmap", "service-enumeration") } else { @("rest", "long-poll", "websocket") }
            capacity = if ($kind -eq "scanner") { 8 } else { 500 }
            current_load = 1
            version = "smoke"
        } | Out-Null
    }
}

if ($RunReconScan) {
    Invoke-Json -Method POST -Uri "$ApiBase/scan-jobs" -Headers $c2Headers -Body @{
        module = "builtin.portscan"
        args = @{
            targets = @("127.0.0.1")
            port_range = "1-1"
            timeout_ms = 250
            max_threads = 4
            scan_engine = "nmap"
            scan_technique = "tcp-connect"
            timing_template = 3
            service_detection = $false
            os_detection = $false
            dns_resolution = $false
            execution_target = "auto"
        }
    } | Out-Null
}

$summary = Invoke-Json -Method GET -Uri "$ApiBase/dashboard/summary" -Headers $c2Headers

Write-Host "Seeded Xero smoke data with prefix '$Prefix'."
Write-Host "Beacons: $($seededBeacons.Count)"
Write-Host "Traffic profile: $($profile.name)"
Write-Host "Dashboard beacon total: $($summary.beacons.total)"
