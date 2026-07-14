#!/usr/bin/env bash
# Builds the FastAPI backend into a standalone executable via PyInstaller,
# for bundling into the Electron app as an extraResource. On Windows use
# scripts/build-backend.ps1 instead - this script is for Linux/Mac
# maintainers and as a same-OS smoke test of the PyInstaller setup (it
# cannot produce a Windows .exe when run on Linux/Mac).
set -euo pipefail
cd "$(dirname "$0")/../backend"

python3 -m venv .build-venv
source .build-venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

pyinstaller --noconfirm --clean --onedir \
  --name "Battery Literature AI Backend" \
  --collect-all uvicorn \
  run_server.py

echo "Backend build complete: backend/dist/Battery Literature AI Backend"
