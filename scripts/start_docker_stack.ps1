# Start API + PostgreSQL in Docker; optional Access data import.
# Usage: .\scripts\start_docker_stack.ps1
#        .\scripts\start_docker_stack.ps1 -Import

param(
    [switch]$Import
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker not found. Start Docker Desktop."
}

$port8000 = netstat -ano | Select-String ":8000\s+.*LISTENING"
if ($port8000) {
    $dockerApi = docker ps --filter "name=api" --format "{{.Names}}" 2>$null
    if (-not $dockerApi) {
        Write-Warning "Port 8000 is busy (local Python?). Run: .\scripts\stop_local_api.ps1"
    }
}

Write-Host "=== docker compose up ===" -ForegroundColor Cyan
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=== waiting for API (up to 90s) ===" -ForegroundColor Cyan
$ok = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:8000/api/" -UseBasicParsing -TimeoutSec 3
        if ($r.StatusCode -eq 200) { $ok = $true; break }
    } catch { Start-Sleep -Seconds 3 }
}
if (-not $ok) {
    Write-Warning "API not ready. Check: docker compose logs api"
} else {
    Write-Host "API ready: http://localhost:8000" -ForegroundColor Green
}

if ($Import) {
    Write-Host "=== import data to Docker PostgreSQL ===" -ForegroundColor Cyan
    Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
    & "$Root\.venv\Scripts\python.exe" "$Root\scripts\restore_db_from_access.py"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host ""
Write-Host "Done." -ForegroundColor Green
Write-Host "  Swagger: http://localhost:8000/docs"
Write-Host "  Client:  dist\OON-PKR-Awards\OON-PKR-Awards.exe"
Write-Host "  Dev:     cd client; python main.py"
