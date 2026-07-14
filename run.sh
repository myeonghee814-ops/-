#!/usr/bin/env bash
# Starts the BLIP backend (FastAPI) and frontend (Vite) for local development.
# Backend runs in the background; frontend runs in the foreground.
# Ctrl+C stops the frontend and automatically stops the backend too.
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "== Backend =="
cd "$ROOT_DIR/backend"
if [ ! -d ".venv" ]; then
  echo "Creating virtualenv..."
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Created backend/.env from .env.example (edit it to add OPENAI_API_KEY if needed)"
fi

echo "Starting backend on http://localhost:8000 ..."
uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!
deactivate

cleanup() {
  echo ""
  echo "Stopping backend (pid $BACKEND_PID)..."
  kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo ""
echo "== Frontend =="
cd "$ROOT_DIR/frontend"
if [ ! -f ".env" ]; then
  cp .env.example .env
fi
if [ ! -d "node_modules" ]; then
  echo "Installing frontend dependencies..."
  npm install
fi

echo "Starting frontend on http://localhost:5173 ..."
npm run dev
