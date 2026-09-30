# PowerShell Launcher for IRCTC Assistant
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$irctcPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $irctcPython)) {
    $irctcPython = (Get-Command python -ErrorAction Stop).Source
}

Write-Host "Starting Personal IRCTC Booking Assistant + CRM..." -ForegroundColor Green

# Clear any zombie on port 8000
$portProcess = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
if ($portProcess) {
    Write-Host "Clearing existing process on port 8000 (PID: $portProcess)..." -ForegroundColor Yellow
    Stop-Process -Id $portProcess -Force -ErrorAction SilentlyContinue
}

# Start Unified FastAPI + UI Server
Start-Process -FilePath $irctcPython -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000' -WorkingDirectory "$projectRoot\backend" -WindowStyle Hidden

Start-Sleep -Seconds 2

# Open in default browser
Start-Process "http://127.0.0.1:8000"

Write-Host "Server is running at http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "API Documentation: http://127.0.0.1:8000/docs" -ForegroundColor Yellow
