@echo off
REM Starts the BLIP backend (FastAPI) and frontend (Vite) for local development.
REM Opens two separate windows, one per server. Close either window to stop it.
setlocal

set "ROOT=%~dp0"

echo == Backend ==
cd /d "%ROOT%backend"
if not exist .venv (
    echo Creating virtualenv...
    python -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
if not exist .env (
    copy .env.example .env >nul
    echo Created backend\.env from .env.example ^(edit it to add OPENAI_API_KEY if needed^)
)
start "BLIP Backend" cmd /k "cd /d "%ROOT%backend" && call .venv\Scripts\activate.bat && uvicorn main:app --reload --port 8000"

echo == Frontend ==
cd /d "%ROOT%frontend"
if not exist .env (
    copy .env.example .env >nul
)
if not exist node_modules (
    echo Installing frontend dependencies...
    call npm install
)
start "BLIP Frontend" cmd /k "cd /d "%ROOT%frontend" && npm run dev"

echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173
endlocal
