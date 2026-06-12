# Stop a local Python/uvicorn process listening on port 8000 (not Docker).
# Use before Docker-only testing: .\scripts\stop_local_api.ps1

$ErrorActionPreference = "Stop"
$listeners = netstat -ano | Select-String "127\.0\.0\.1:8000\s+.*LISTENING|0\.0\.0\.0:8000\s+.*LISTENING"
if (-not $listeners) {
    Write-Host "Port 8000 is free." -ForegroundColor Green
    exit 0
}

$procIds = @()
foreach ($line in $listeners) {
    $parts = ($line -replace '\s+', ' ').ToString().Trim().Split(' ')
    $procId = [int]$parts[-1]
    if ($procId -gt 0) { $procIds += $procId }
}
$procIds = $procIds | Select-Object -Unique

foreach ($procId in $procIds) {
    $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
    if (-not $proc) { continue }
    if ($proc.ProcessName -notmatch '^(python|pythonw|uvicorn)$') {
        Write-Host "Port 8000: PID $procId ($($proc.ProcessName)) - not a Python server, skipped."
        continue
    }
    Write-Host "Stopping local API: PID $procId ($($proc.ProcessName))" -ForegroundColor Yellow
    Stop-Process -Id $procId -Force
}

Write-Host "Done. Start Docker: .\scripts\start_docker_stack.ps1" -ForegroundColor Cyan
