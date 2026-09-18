# DentAI Flow - restore a dump into LOCAL docker Postgres
# Does NOT write to live Neon.
#
# Usage:
#   powershell -File scripts/restore.ps1 -File backups/dentai_neon_20260918_223000.dump
# Confirm with: EVET

param(
    [Parameter(Mandatory = $true)]
    [string]$File
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$dump = $File
if (-not [System.IO.Path]::IsPathRooted($dump)) {
    $dump = Join-Path $Root $File
}
if (-not (Test-Path $dump)) { throw "Backup not found: $dump" }

$container = if ($env:CONTAINER_NAME) { $env:CONTAINER_NAME } else { "dentai_postgres" }
$running = docker ps --format "{{.Names}}" 2>$null | Where-Object { $_ -eq $container }
if (-not $running) { throw "Local Postgres not running ($container). Start with: docker compose up -d postgres" }

function Get-EnvValue([string]$Key) {
    $line = Get-Content (Join-Path $Root ".env") -Encoding UTF8 |
        Where-Object { $_ -match "^$Key=" } |
        Select-Object -First 1
    if (-not $line) { return $null }
    return $line.Substring("$Key=".Length).Trim().Trim('"').Trim("'")
}

$pgUser = Get-EnvValue "POSTGRES_USER"; if (-not $pgUser) { $pgUser = "dentai" }
$pgDb = Get-EnvValue "POSTGRES_DB"; if (-not $pgDb) { $pgDb = "dentai_db" }

Write-Host "WARNING: local database '$pgDb' will be dropped and replaced from $dump"
Write-Host "Live Neon is not touched. Type EVET to continue:"
$confirm = Read-Host
if ($confirm -ne "EVET") {
    Write-Host "Cancelled."
    exit 0
}

$remote = "/tmp/dentai_restore.dump"
docker cp $dump "${container}:${remote}"
docker exec $container psql -U $pgUser -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$pgDb' AND pid <> pg_backend_pid();" | Out-Null
docker exec $container psql -U $pgUser -d postgres -c "DROP DATABASE IF EXISTS $pgDb;"
docker exec $container psql -U $pgUser -d postgres -c "CREATE DATABASE $pgDb OWNER $pgUser;"
docker exec $container pg_restore -U $pgUser -d $pgDb --no-owner --no-acl --clean --if-exists $remote
docker exec $container rm -f $remote | Out-Null
Write-Host "Local restore done. Restart: docker compose restart api ui"
