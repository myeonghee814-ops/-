# BLIP — Battery Literature Intelligence Platform

BLIP helps battery researchers search, organize, summarize, and compare
recent battery electrolyte papers.

**Status:** literature search (Semantic Scholar with automatic OpenAlex
fallback), AI paper analysis, an AI comparison engine, and Excel export of
selected papers (summary + experimental conditions + AI summary +
cross-paper comparison, styled with openpyxl) are all implemented and
wired together — select papers in the search results grid and export them
to get a full AI-analyzed report. The paper detail page's own "Quick
Summary" cards are still static placeholders, though — see
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full list of design
decisions and what's intentionally missing so far.

## Tech stack

| Layer      | Choices |
|------------|---------|
| Frontend   | React, Vite, TypeScript, TailwindCSS, React Router, TanStack Query, AG Grid |
| Backend    | FastAPI, SQLAlchemy (async), SQLite (dev) / PostgreSQL (future), Pydantic |
| Deployment | Docker, Docker Compose |

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
│   ├── core/           # Settings, logging, caching
│   ├── prompts/        # LLM prompt templates
│   ├── utils/          # Shared helpers
│   ├── tests/
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
├── docker/              # Reserved for future deployment assets
├── docs/
│   └── ARCHITECTURE.md
└── docker-compose.yml
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
Health check: http://localhost:8000/api/v1/health
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

### Frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

App: http://localhost:5173

### Docker (local dev)

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
docker compose up --build
```

This runs both services with source mounted for live reload. It is **not**
a production deployment setup — see `docs/ARCHITECTURE.md`.

## Roadmap

- [x] Literature search (`GET /api/search`, Semantic Scholar + OpenAlex fallback)
- [x] AI paper analysis (`POST /api/v1/analyze`, OpenAI Responses API)
- [x] AI comparison engine (`POST /api/v1/compare`)
- [x] Excel export of selected papers (`POST /api/v1/export`, openpyxl)
- [ ] Wire AI analysis/comparison into the paper detail page itself
- [ ] Persisting/organizing searched papers (ingestion into the `papers` table)
- [ ] PostgreSQL migration + Alembic
- [ ] Production Docker build
