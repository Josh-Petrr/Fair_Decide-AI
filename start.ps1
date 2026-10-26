# FairDecide AI - start everything for a demo:   powershell -ExecutionPolicy Bypass -File start.ps1
$root = $PSScriptRoot
$dockerBin = "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin"
if (-not (Get-Command docker -ErrorAction SilentlyContinue) -and (Test-Path $dockerBin)) { $env:Path = "$dockerBin;$env:Path" }

Write-Host "1/4  Database + demo mailbox (Docker)..." -ForegroundColor Cyan
docker compose -f "$root\docker-compose.yml" up -d
if ($LASTEXITCODE -ne 0) { Write-Host "Docker is not running - start Docker Desktop and try again." -ForegroundColor Red; exit 1 }

Write-Host "2/4  Resetting demo data to a clean state..." -ForegroundColor Cyan
& "$root\.venv\Scripts\python.exe" -m backend.admin reset

Write-Host "3/4  API on http://localhost:8000 ..." -ForegroundColor Cyan
Start-Process powershell -WorkingDirectory $root -ArgumentList "-NoExit", "-Command", "& '.\.venv\Scripts\python.exe' -m uvicorn backend.main:app --port 8000"

Write-Host "4/4  Web app on http://localhost:5173 ..." -ForegroundColor Cyan
Start-Process powershell -WorkingDirectory "$root\frontend" -ArgumentList "-NoExit", "-Command", "npm run dev"

Start-Sleep -Seconds 6
Start-Process "http://localhost:5173"
Start-Process "http://localhost:8025"
Write-Host "Ready. App: http://localhost:5173   Demo inbox: http://localhost:8025" -ForegroundColor Green
