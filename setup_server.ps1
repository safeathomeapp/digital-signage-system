$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "Digital Signage Server setup"
Write-Host "Root: $root"
Write-Host ""

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python is not available on PATH. Install Python 3.13+ first."
    exit 1
}

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

$py = Join-Path $root ".venv\Scripts\python.exe"

Write-Host "Upgrading pip..."
& $py -m pip install --upgrade pip

Write-Host "Installing dependencies..."
& $py -m pip install -r requirements.txt

if (-not (Test-Path "uploads")) {
    New-Item -ItemType Directory -Path "uploads" | Out-Null
}
if (-not (Test-Path "logs")) {
    New-Item -ItemType Directory -Path "logs" | Out-Null
}

Write-Host "Initializing database and settings..."
& $py -c "import production_app as p; p.init_db(); p.upgrade_database(); p._ensure_default_pin(); print('Initialization complete.')"

Write-Host ""
Write-Host "Setup complete."
Write-Host "Next: run start_server.bat to launch the server."
