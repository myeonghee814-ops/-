#Requires -Version 5.1
# Builds the FastAPI backend into a standalone Windows executable
# ("Battery Literature AI Backend.exe") via PyInstaller, for bundling into
# the Electron app as an extraResource. Run on Windows with Python 3.11+.

$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot/../backend"

python -m venv .build-venv
& ".build-venv/Scripts/Activate.ps1"

pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

pyinstaller --noconfirm --clean --onedir `
  --name "Battery Literature AI Backend" `
  --collect-all uvicorn `
  run_server.py

Write-Host "Backend build complete: backend/dist/Battery Literature AI Backend"
