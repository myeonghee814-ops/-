# BLIP — Battery Literature Intelligence Platform

BLIP helps battery researchers search, organize, summarize, and compare
recent battery electrolyte papers.

**Status:** literature search (Semantic Scholar with automatic OpenAlex
fallback), AI paper analysis, an AI comparison engine, and Excel export of
selected papers (summary + experimental conditions + AI summary +
cross-paper comparison, styled with openpyxl) are all implemented and
wired together — select papers in the search results grid and export them
to get a full AI-analyzed report. The project also has a production-shaped
deployment path: multi-stage Docker images, a Postgres + Alembic migration
path, structured/JSON logging, request tracing, Prometheus metrics, and
authentication scaffolding (no login yet). The paper detail page's own
"Quick Summary" cards are still static placeholders — see
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
compares them, then returns a 4-sheet `.xlsx` file

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

## Roadmap

- [x] Literature search (`GET /api/search`, Semantic Scholar + OpenAlex fallback)
- [x] AI paper analysis (`POST /api/v1/analyze`, OpenAI Responses API)
- [x] AI comparison engine (`POST /api/v1/compare`)
- [x] Excel export of selected papers (`POST /api/v1/export`, openpyxl)
- [x] Production Docker images, Postgres + Alembic, logging/monitoring, auth placeholders
- [ ] Wire AI analysis/comparison into the paper detail page itself
- [ ] Persisting/organizing searched papers (ingestion into the `papers` table)
- [ ] Real user authentication (login/signup, built on the existing placeholders)
- [ ] TLS/ingress, CI/CD, secrets manager integration
