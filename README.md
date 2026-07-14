# BLIP — Battery Literature Intelligence Platform

BLIP is a literature analysis tool for battery electrolyte researchers —
not a generic paper search engine. Every feature is built to do one of
five things: reduce reading time, increase scientific accuracy, make
papers easy to compare, extract experimental conditions into structured
data, or present information more cleanly. A researcher should be able to
learn in five minutes what used to take reading ten papers.

**Status:** literature search (Semantic Scholar with automatic OpenAlex
fallback) returns a compact results table (Title, Journal, Year, Citation
Count, Battery System, Electrolyte, Main Contribution — the last three
AI-derived, filled in on demand via "Analyze Results"). AI paper analysis
extracts structured experimental conditions per paper; the paper detail
page presents them as a scannable, <30-second "Experimental Conditions"
card alongside Key Experimental Results/Advantages/Limitations/AI Summary.
A dedicated Paper Comparison page lets you select multiple papers and get
an AI-generated cross-paper comparison table (electrolyte, salt,
additives, cathode, anode, voltage window, temperature, cycle condition,
main finding, advantages, limitations). Excel export (4 formatted sheets:
Paper Summary, Experimental Conditions, AI Summary, Comparison) works from
both the search page and the comparison page. The project also has a
production-shaped deployment path: multi-stage Docker images, a Postgres +
Alembic migration path, structured/JSON logging, request tracing,
Prometheus metrics, and authentication scaffolding (no login yet) — see
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full list of design
decisions and what's intentionally missing so far.

## Tech stack

| Layer      | Choices |
|------------|---------|
| Frontend   | React, Vite, TypeScript, TailwindCSS, React Router, TanStack Query, AG Grid |
| Backend    | FastAPI, SQLAlchemy (async), SQLite (dev) / PostgreSQL (prod), Alembic, Pydantic |
| Deployment | Docker (multi-stage), Docker Compose, nginx, gunicorn+uvicorn |
| Ops        | Prometheus metrics, structured JSON logging, request tracing |

## Project structure

```
.
├── backend/
│   ├── api/            # Routes (HTTP layer only)
│   ├── services/       # Business logic
│   │   └── external/   # Provider API clients (Semantic Scholar, OpenAlex, OpenAI)
│   ├── models/         # SQLAlchemy ORM models
│   ├── schemas/        # Pydantic request/response models
│   ├── database/       # Engine/session setup
│   ├── core/           # Settings, logging, middleware, metrics, caching,
│   │                   # shared HTTP clients, security helpers
│   ├── alembic/         # Database migrations
│   ├── prompts/        # LLM prompt templates
│   ├── utils/          # Shared helpers
│   ├── tests/
│   ├── entrypoint.sh    # Production container entrypoint (runs migrations, then serves)
│   └── main.py
├── frontend/
│   └── src/
│       ├── components/
│       ├── pages/
│       ├── layouts/
│       ├── hooks/
│       ├── services/   # API client calls
│       ├── types/
│       └── assets/
├── docs/
│   └── ARCHITECTURE.md
├── docker-compose.yml       # Local development (SQLite, hot reload)
├── docker-compose.prod.yml  # Production-shaped stack (Postgres, nginx, gunicorn)
└── .env.prod.example        # Compose-level secrets for docker-compose.prod.yml
```

## Getting started

### Quick start (one command)

```bash
./run.sh          # macOS / Linux
run.bat           # Windows
```

Sets up both the backend virtualenv and frontend `node_modules` on first
run (copying `.env.example` → `.env` for each if missing), then starts the
backend on :8000 and the frontend on :5173. On `run.sh`, Ctrl+C stops both
servers; on `run.bat`, each server runs in its own window.

### Desktop shortcut (Windows, no visible console)

For end users who just want to double-click an icon — see
[`desktop/README.md`](desktop/README.md) for the one-time setup
(`Create-Desktop-Shortcut.vbs`) and how it works: a hidden PowerShell
process sets up/starts both servers, waits until they're actually
responding, then opens Chrome in app mode. `desktop/start.ps1` and
`desktop/stop.ps1` are the underlying scripts if you want to read or
adapt them.

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload
```

API docs: http://localhost:8000/docs
Health check (liveness): http://localhost:8000/api/v1/health
Readiness (checks DB): http://localhost:8000/api/v1/health/ready
Prometheus metrics: http://localhost:8000/metrics
Literature search: http://localhost:8000/api/search?keyword=electrolyte&year_from=2020&year_to=2024&limit=10
AI paper analysis: `POST http://localhost:8000/api/v1/analyze` with a JSON body
of `{"title": "...", "abstract": "..."}` (requires `OPENAI_API_KEY` in `.env`)
AI comparison: `POST http://localhost:8000/api/v1/compare` with a JSON body of
`{"analyses": [...]}` — at least `COMPARISON_MIN_PAPERS` (default 10) results
from `/analyze`
Excel export: `POST http://localhost:8000/api/v1/export` with a JSON body of
`{"papers": [...]}` (search results) — analyzes and, if enough succeed,
compares them, then returns a 4-sheet `.xlsx` file (Paper Summary,
Experimental Conditions, AI Summary, Comparison)

Run tests:

```bash
pytest
```

Database migrations (Alembic):

```bash
alembic upgrade head        # apply all pending migrations
alembic revision --autogenerate -m "describe the change"   # after editing models/
alembic downgrade -1         # roll back one migration
```

### Frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

App: http://localhost:5173

### Docker — local development

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
docker compose up --build
```

SQLite, hot reload on both services. **Not** a production deployment — see
below.

### Docker — production-shaped stack

```bash
cp .env.prod.example .env
# edit .env: set POSTGRES_PASSWORD, CORS_ORIGINS, SECRET_KEY (and
# OPENAI_API_KEY if you want AI features), then:
docker compose -f docker-compose.prod.yml up --build -d
```

Runs Postgres, the backend behind gunicorn (multi-worker, migrations
applied automatically on startup), and the frontend's static build served
by nginx (which also reverse-proxies `/api/` to the backend — the only
port published to the host is the frontend's 80). Compose refuses to start
without `POSTGRES_PASSWORD`/`CORS_ORIGINS`/`SECRET_KEY` set, rather than
silently booting with insecure defaults.

This still doesn't include TLS termination, a CI/CD pipeline, or a secrets
manager — see "What's deliberately not here yet" in `docs/ARCHITECTURE.md`
for the full list of what a further production hardening pass would add.

## Packaging as a standalone desktop app (.exe)

Not implemented yet — this is a design note for turning BLIP into a real
installable program instead of "two dev servers + a shortcut script."

**Recommendation: Tauri, not Electron.** Tauri wraps the OS's built-in
webview (WebView2 on Windows, already present on Win10 21H2+/Win11)
instead of bundling Chromium, so the installer is single-digit MB instead
of 100MB+, and idle memory use is far lower. The tradeoff is a Rust build
toolchain and, on older Windows installs, a one-time ~150KB WebView2
bootstrapper. Electron is the safer choice only if pixel-identical
rendering across every Windows version matters more than install size —
not the case here.

**The real work either way is the Python backend**, since neither Tauri
nor Electron can run it directly:

1. Freeze the backend into a native binary: `pyinstaller --onefile
   backend/main.py` (as an ASGI app, invoke it via a small entry script
   that calls `uvicorn.run(app, port=8000)` rather than the `uvicorn`
   CLI, since PyInstaller can't discover `main:app` the way the CLI does).
2. Have FastAPI serve the built frontend (`frontend/dist/`) itself via
   `StaticFiles`, so the packaged app is a single backend process on one
   port — no separate frontend dev server to manage at runtime. (Vite's
   dev server stays dev-only; `npm run build` output gets mounted instead.)
3. Register that frozen binary as a Tauri "sidecar": Tauri spawns it on
   app launch and kills it on window close, and the webview points at
   `http://localhost:8000` once a readiness check passes (same idea as
   `desktop/start.ps1`'s `Wait-ForUrl`, but inside the Rust shell instead
   of PowerShell).
4. `tauri build` produces a normal Windows installer (`.msi`/NSIS `.exe`)
   that installs to Program Files and creates its own Start Menu/Desktop
   shortcuts — replacing the `desktop/*.vbs` shortcut hack entirely.

Effort is roughly a day of focused work (PyInstaller spec + hidden-import
fixes for FastAPI/SQLAlchemy/openpyxl/the OpenAI SDK, Tauri sidecar
config, one Windows machine to actually build and test on — this repo's
sandbox can't produce or verify a Windows `.exe`). Worth doing once the
UI stabilizes; premature before that, since every UI change means
re-verifying the packaged build too.

## Roadmap

- [x] Literature search (`GET /api/search`, Semantic Scholar + OpenAlex fallback)
- [x] AI paper analysis (`POST /api/v1/analyze`, OpenAI Responses API)
- [x] AI comparison engine (`POST /api/v1/compare`)
- [x] Excel export of selected papers (`POST /api/v1/export`, openpyxl)
- [x] Production Docker images, Postgres + Alembic, logging/monitoring, auth placeholders
- [x] Battery-research-focused search table, paper detail page, and a dedicated Paper Comparison page
- [ ] Persisting/organizing searched papers (ingestion into the `papers` table)
- [ ] Caching AI analyses so the same paper isn't re-sent to OpenAI across Analyze/Compare/Export
- [ ] Real user authentication (login/signup, built on the existing placeholders)
- [ ] TLS/ingress, CI/CD, secrets manager integration
