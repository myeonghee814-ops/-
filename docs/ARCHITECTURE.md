# BLIP Architecture

This document explains the design decisions behind the project. Literature
search (`GET /api/search`) is implemented; summarization/comparison are not
yet — this describes the scaffolding those remaining features will be built on.

## Layering (backend)

```
api/               HTTP concerns only: routing, request/response models, status codes
services/          Business logic, orchestration
services/external/ Provider-specific API clients (Semantic Scholar, OpenAlex)
models/            SQLAlchemy ORM models — the persistence shape
schemas/           Pydantic models — the API contract shape
database/          Engine/session lifecycle, declarative base
core/              Cross-cutting concerns: settings, logging, caching
prompts/           LLM prompt templates (future summarization/comparison features)
utils/             Small stateless helpers with no business meaning of their own
```

Routes never touch SQLAlchemy directly — they call a service, which
returns ORM objects that FastAPI serializes via a Pydantic schema
(`response_model=...`). This keeps three concerns separable:

- **models vs schemas**: the database shape and the API shape are allowed
  to diverge (e.g. hiding internal fields, renaming for the frontend,
  versioning the API) without touching the table definition.
- **routes vs services**: routes stay a thin, easily-testable HTTP layer;
  services hold logic that will grow substantially once literature
  search/summarization is implemented, without bloating route handlers.

## Why async SQLAlchemy + SQLite now, Postgres later

`DATABASE_URL` is the only thing that changes between environments
(`sqlite+aiosqlite:///./blip.db` locally, `postgresql+asyncpg://...` in
production) because the codebase only ever talks to SQLAlchemy's async
engine/session API, never to a driver directly. Async is used from the
start (`AsyncSession`, `async def` routes) so adopting Postgres later is a
config change, not a rewrite of every endpoint.

## Configuration: pydantic-settings

`core/config.py` defines a single `Settings` object loaded from a `.env`
file (via `pydantic-settings`) with environment variables always able to
override it. This gives:

- type validation of config at startup (fail fast on a bad value) instead
  of at first use deep in the code
- one place to see every configurable value
- a `cors_origins_list` property so `CORS_ORIGINS` can be a plain
  comma-separated string in `.env` rather than requiring JSON escaping

`get_settings()` is `lru_cache`d so the `.env` file is parsed once per
process and can be swapped for a FastAPI dependency override in tests.

## Logging

`core/logging.py` configures the root logger once, at import time in
`main.py`, via `logging.config.dictConfig`. Every module then just calls
`logging.getLogger(__name__)` and inherits consistent formatting — no
per-module handler setup, and `LOG_LEVEL` is an env var like everything
else.

## CORS

Enabled via `CORSMiddleware` in `main.py`, with allowed origins coming
from `settings.cors_origins_list`. Locally this is the Vite dev server
(`http://localhost:5173`); in Docker Compose it's set through the
`CORS_ORIGINS` environment variable so no code change is needed to add a
production frontend origin.

## Lifespan over `@app.on_event`

`main.py` uses FastAPI's `lifespan` async context manager rather than the
deprecated `@app.on_event("startup"/"shutdown")` decorators — this is the
currently-recommended pattern and is where DB connection warm-up, cache
clients, etc. will be added as the app grows.

## Frontend structure

```
components/   Reusable, presentation-only UI pieces
pages/        Route-level components (one per URL)
layouts/      Shared page chrome (header/nav) wrapping pages via <Outlet/>
hooks/        Reusable stateful logic, mostly TanStack Query wrappers
services/     All HTTP calls — pages/components never call axios directly
types/        Shared TypeScript types, mirroring backend Pydantic schemas
```

- **TanStack Query** owns all server state (caching, loading/error state,
  refetching) so components don't hand-roll `useEffect` + `useState` data
  fetching. `useHealthCheck` is the template every future data hook follows.
- **services/** isolates the HTTP layer: if the API contract changes,
  only the relevant `*Service.ts` file changes, not every component that
  uses it.
- **AG Grid** is installed as a dependency now because comparing large
  sets of papers (sorting/filtering/pinning columns) is the core future
  feature it's chosen for, but no grid is wired up yet.
- The Vite dev server proxies `/api` to the backend (`vite.config.ts`), so
  in development the frontend can call relative paths and never needs
  `VITE_API_BASE_URL` set; in Docker/production that env var points
  directly at the deployed backend origin.

## Literature search (`GET /api/search`)

Input: `keyword`, `year_from`/`year_to`, `limit` — validated by
`schemas/search.py::SearchQuery` (cross-field check: `year_from <= year_to`).
Output: normalized `PaperResult` objects (title, authors, journal, year,
citation count, DOI, abstract, PDF URL if available, published date).

**API logic vs. service layer.** `services/external/semantic_scholar_client.py`
and `services/external/openalex_client.py` each own one provider's request
building and response parsing, and only ever raise their own exception
(`SemanticScholarError` / `OpenAlexError`). `services/search_service.py`
knows nothing about either provider's HTTP shape — it just calls Semantic
Scholar, catches its exception on failure, calls OpenAlex instead, and
raises `ExternalSearchError` only if both fail. This means adding a third
provider means writing one new client module and one new `except` clause,
never touching parsing code for the other two.

**Exception handling.** Every external call is wrapped so network errors,
non-2xx responses, and unexpected JSON shapes all normalize to a typed
exception instead of leaking `httpx`/`KeyError` internals to the route.
The route (`api/routes/search.py`) turns `ExternalSearchError` into a 502
and a pydantic `ValidationError` (e.g. bad year range) into a 422 — callers
never see a raw 500.

**Caching.** `core/cache.py::TTLCache` is a small in-process, dependency-free
cache keyed by `(keyword, year_from, year_to, limit)`, with a
`SEARCH_CACHE_TTL_SECONDS` env var controlling its lifetime. It exists to
avoid hammering rate-limited public APIs with repeated identical queries.
It's intentionally not Redis: there's only one backend process right now,
and the `get`/`set` interface is small enough to swap to a Redis-backed
version later without touching `search_service.py`.

## Docker

Each service has its own `Dockerfile`; the root `docker-compose.yml` runs
both for local development with source mounted as a volume (live reload).
The frontend image currently just runs `npm run dev` — a production
multi-stage build (static `vite build` output served by nginx) is
intentionally deferred to `docker/` until deployment is actually
implemented, per project scope. A Postgres service is noted but commented
out in `docker-compose.yml` until the project needs it.

## What's deliberately not here yet

- No persistence of search results (search is live-only; nothing is written
  to the `papers` table yet — that's a separate "ingestion" concern)
- No summarization/comparison logic (hence the currently-empty `prompts/`)
- No auth/user accounts
- No Alembic migrations (SQLite schema is created ad hoc during this
  scaffolding phase; Alembic should be introduced alongside the first real
  migration, once the schema stabilizes)
- No production Docker/deployment pipeline

These are out of scope for this skeleton by design.
