# DentAI Flow - Windows backup
# Code is already on GitHub. This script dumps data:
#   neon  = live Neon Postgres
#   local = docker dentai_postgres
#
# Usage:
#   powershell -File scripts/backup.ps1
#   powershell -File scripts/backup.ps1 -Target neon
#   powershell -File scripts/backup.ps1 -Target local

param(
    [ValidateSet("both", "neon", "local")]
    [string]$Target = "both",
    [int]$RetentionDays = 14
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$PgDump = "C:\Program Files\PostgreSQL\17\bin\pg_dump.exe"
if (-not (Test-Path $PgDump)) {
    throw "pg_dump not found: $PgDump"
}

$BackupDir = Join-Path $Root "backups"
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"

function Get-EnvValue([string]$Key) {
    $line = Get-Content (Join-Path $Root ".env") -Encoding UTF8 |
        Where-Object { $_ -match "^$Key=" } |
        Select-Object -First 1
    if (-not $line) { return $null }
    return $line.Substring("$Key=".Length).Trim().Trim('"').Trim("'")
}

function Normalize-PgUrl([string]$Url) {
    $Url = $Url -replace "^postgresql\+asyncpg://", "postgresql://"
    $Url = $Url -replace "^postgres://", "postgresql://"
    $Url = $Url -replace "[?&]ssl=require", ""
    $Url = $Url.TrimEnd("?", "&")
    if ($Url -match "neon\.tech" -and $Url -notmatch "sslmode=") {
        $sep = if ($Url.Contains("?")) { "&" } else { "?" }
        $Url = "$Url${sep}sslmode=require"
    }
    return $Url
}

function Invoke-Dump([string]$Name, [scriptblock]$Dump) {
    $file = Join-Path $BackupDir "dentai_${Name}_$Stamp.dump"
    Write-Host "[$(Get-Date -Format o)] $Name backup starting"
    & $Dump $file
    if ($LASTEXITCODE -ne 0) { throw "$Name pg_dump exit=$LASTEXITCODE" }
    if (-not (Test-Path $file) -or (Get-Item $file).Length -lt 1024) {
        throw "$Name backup empty or too small: $file"
    }
    $size = (Get-Item $file).Length
    Write-Host "[$(Get-Date -Format o)] $Name done: $file ($size bytes)"
}

if ($Target -in @("both", "neon")) {
    $raw = Get-EnvValue "DATABASE_URL"
    if (-not $raw) { throw "DATABASE_URL missing in .env (needed for Neon backup)" }
    $url = Normalize-PgUrl $raw
    $hostPart = ($url -split "@")[-1].Split("/")[0]
    Write-Host "Neon host=$hostPart"
    Invoke-Dump "neon" {
        param($file)
        & $PgDump $url --no-owner --no-acl -Fc -f $file
    }
}

if ($Target -in @("both", "local")) {
    $container = if ($env:CONTAINER_NAME) { $env:CONTAINER_NAME } else { "dentai_postgres" }
    $running = docker ps --format "{{.Names}}" 2>$null | Where-Object { $_ -eq $container }
    if (-not $running) {
        Write-Host "Local $container is not running - skipping local backup"
    } else {
        $pgUser = Get-EnvValue "POSTGRES_USER"; if (-not $pgUser) { $pgUser = "dentai" }
        $pgDb = Get-EnvValue "POSTGRES_DB"; if (-not $pgDb) { $pgDb = "dentai_db" }
        Invoke-Dump "local" {
            param($file)
            $tmp = "/tmp/dentai_backup.dump"
            docker exec $container pg_dump -U $pgUser -d $pgDb --no-owner --no-acl -Fc -f $tmp
            if ($LASTEXITCODE -ne 0) { throw "docker pg_dump exit=$LASTEXITCODE" }
            docker cp "${container}:${tmp}" $file
            docker exec $container rm -f $tmp | Out-Null
        }
    }
}

$cutoff = (Get-Date).AddDays(-$RetentionDays)
Get-ChildItem $BackupDir -Filter "dentai_*.dump" -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -lt $cutoff } |
    ForEach-Object {
        Remove-Item $_.FullName -Force
        Write-Host "Removed old backup: $($_.Name)"
    }

Write-Host "Backup folder: $BackupDir"
Write-Host "Code backup: git/GitHub. Dump files are gitignored."
