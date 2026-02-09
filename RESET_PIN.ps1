$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if (-not (Test-Path ".venv\\Scripts\\python.exe")) {
    Write-Host "Virtual environment not found."
    Write-Host "Run setup_server.ps1 first."
    exit 1
}

Write-Host "Starting server with temporary PIN 1234..."
$env:SIGNAGE_ADMIN_PIN = "1234"
& ".venv\\Scripts\\python.exe" production_app.py
