<#
.SYNOPSIS
Starts the local Xero Docker Compose stacks with one command.

.EXAMPLE
.\scripts\install-local.ps1

.EXAMPLE
.\scripts\install-local.ps1 -IncludeScaffolds -SeedSmoke
#>
[CmdletBinding()]
param(
    [switch]$SkipEnvCopy,
    [switch]$NoBuild,
    [switch]$IncludeScaffolds,
    [switch]$SeedSmoke,
    [int]$HealthTimeoutSeconds = 180,
    [string]$FrontendUrl = "http://localhost:3000",
    [string]$BffUrl = "http://localhost:8000",
    [string]$C2Url = "http://localhost:8001",
    [string]$HandlerUrl = "http://localhost:8002",
    [string]$ScannerUrl = "http://localhost:8003"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$PlatformDir = Join-Path $RepoRoot "platform"

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found on PATH."
    }
}

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

function Wait-HttpReady {
    param(
        [string]$Name,
        [string]$Url,
        [int]$TimeoutSeconds
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) {
                Write-Host "$Name is ready: $Url"
                return
            }
        }
        catch {
            Start-Sleep -Seconds 2
        }
    }
    throw "$Name did not become ready before timeout: $Url"
}

Require-Command "docker"

$envExample = Join-Path $PlatformDir ".env.example"
$envFile = Join-Path $PlatformDir ".env"
if (-not $SkipEnvCopy -and -not (Test-Path $envFile) -and (Test-Path $envExample)) {
    Copy-Item $envExample $envFile
    Write-Host "Created platform\.env from platform\.env.example."
}

$upArgs = @("up", "-d")
if (-not $NoBuild) {
    $upArgs += "--build"
}

Write-Host "Starting local UI/BFF stack..."
Invoke-Compose "docker-compose.bff.yml" $upArgs

Write-Host "Starting local C2 backend stack..."
Invoke-Compose "docker-compose.c2.yml" $upArgs

if ($IncludeScaffolds) {
    Write-Host "Starting optional beacon handler scaffold..."
    Invoke-Compose "docker-compose.handler.yml" $upArgs

    Write-Host "Starting optional scanner scaffold..."
    Invoke-Compose "docker-compose.scanner.yml" $upArgs
}

Wait-HttpReady "BFF API" "$($BffUrl.TrimEnd('/'))/ready" $HealthTimeoutSeconds
Wait-HttpReady "C2 API" "$($C2Url.TrimEnd('/'))/ready" $HealthTimeoutSeconds
Wait-HttpReady "Frontend" "$($FrontendUrl.TrimEnd('/'))/login" $HealthTimeoutSeconds

if ($IncludeScaffolds) {
    Wait-HttpReady "Beacon handler" "$($HandlerUrl.TrimEnd('/'))/ready" $HealthTimeoutSeconds
    Wait-HttpReady "Scanner" "$($ScannerUrl.TrimEnd('/'))/ready" $HealthTimeoutSeconds
}

if ($SeedSmoke) {
    $smokeScript = Join-Path $PSScriptRoot "smoke-data.ps1"
    & $smokeScript -C2Url $C2Url
    if ($LASTEXITCODE -ne 0) {
        throw "Smoke data seeding failed."
    }
}

Write-Host ""
Write-Host "Xero is ready."
Write-Host "Frontend: $FrontendUrl"
Write-Host "BFF API:   $BffUrl"
Write-Host "C2 API:    $C2Url"
