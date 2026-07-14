# BLIP Architecture

This document explains the design decisions behind the project. Literature
search (`GET /api/search`), AI paper analysis (`POST /api/v1/analyze`), and
the AI comparison engine (`POST /api/v1/compare`) are implemented;
persisting/organizing papers is not — this describes the scaffolding that
remaining feature will be built on.

## Layering (backend)

```
api/               HTTP concerns only: routing, request/response models, status codes
services/          Business logic, orchestration
services/external/ Provider-specific API clients (Semantic Scholar, OpenAlex, OpenAI)
models/            SQLAlchemy ORM models — the persistence shape
schemas/           Pydantic models — the API contract shape
database/          Engine/session lifecycle, declarative base
core/              Cross-cutting concerns: settings, logging, caching
prompts/           LLM prompt templates, kept as data separate from services/
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

## AI paper analysis (`POST /api/v1/analyze`)

Input: `title` plus either `abstract` or `pdf_text` (`schemas/analysis.py::AnalyzeRequest`;
a validator rejects requests with neither). Output: `PaperAnalysis` — the full
set of fields the frontend's paper detail "Quick Summary" cards were built to
show (electrolyte, salt, solvent, additive, cathode, anode, separator, cell
type, voltage window, temperature, formation protocol, cycle condition, rate
capability, main findings, innovation, advantages, limitations, future work),
plus title/authors/journal for cross-checking against the source paper.

**Same API-logic/service-layer split as search.** `services/external/openai_client.py`
owns the OpenAI Responses API request/response handling and only raises
`OpenAIAnalysisError`; `services/ai_analysis_service.py` just builds the
prompt content from the request and has no knowledge of the OpenAI SDK.

**Structured output, not prompt-and-hope.** The request uses the Responses
API's strict JSON-schema mode (`text.format.type = "json_schema"`,
`strict: true`) with a schema matching `PaperAnalysis` field-for-field, so
the model is constrained to emit exactly that shape — this is what
guarantees "JSON only, no markdown" rather than relying on prompt wording
alone. The prompt (`prompts/paper_analysis.py`) still states the
JSON-only/no-markdown/no-guessing rules explicitly, as defense in depth and
to steer field content (e.g. "use null rather than inventing a value").

**Nullable, not fabricated.** Every descriptive field is nullable end to
end (schema → prompt instructions → `PaperAnalysis`), because most
abstracts won't mention half of these fields (e.g. formation protocol).
The alternative — coercing missing data into empty strings or invented
values — would silently misinform a researcher relying on this output.

**Not yet wired to the frontend.** The paper detail page's "Quick Summary"
cards (`frontend/src/pages/PaperDetailPage.tsx`) still show static
"not analyzed yet" placeholders. Calling this endpoint from the UI (e.g. an
"Analyze" button + a TanStack Query mutation) is a separate follow-up.

## AI comparison engine (`POST /api/v1/compare`)

Input: a batch of already-analyzed papers — `schemas/comparison.py::ComparisonRequest`
takes `{"analyses": [PaperAnalysis, ...]}`, i.e. output of `/api/v1/analyze`
called once per paper. Output: `ComparisonResult` — common experimental
conditions, differences, frequently used electrolytes/additives, most
common cathode/anode, research trend, research gap, potential future
direction, and a `comparison_table` (one row per input paper: title,
electrolyte, cathode, anode, separator, cell type, voltage window,
temperature) for scanning papers side by side.

**"After 10 papers are analyzed, automatically compare them" — how the batch
size is enforced without persistence.** There's no server-side tracking of
"papers analyzed so far" yet (see "not yet here" below), so this isn't a
background job that fires on a counter. Instead, `services/comparison_service.py`
enforces `settings.COMPARISON_MIN_PAPERS` (default 10) as a precondition: submit
a batch of at least that many analyses and the comparison runs immediately as
part of that same request — no separate "run comparison now" step. Below the
threshold it raises `InsufficientAnalysesError` (→ HTTP 422 with a message
stating how many were provided vs. required). If a real "analyze 10 papers
over time, then auto-trigger" workflow is wanted later, that requires adding
persistence for analyses first (tracking count, associating results with a
research session) — a bigger change than this endpoint, deliberately deferred
along with the rest of persistence.

**The comparison itself is AI-generated, not counted client-side.** Rather
than computing "most common cathode" by tallying exact string matches
ourselves (which would miss that "1M LiPF6" and "LiPF6" describe the same
salt), the entire `ComparisonResult` — including the table — comes from one
OpenAI Responses API call over the batch's already-extracted fields, using
the same strict JSON-schema structured-output approach as `/analyze`
(`services/external/openai_client.py::compare_papers`, sharing its request
plumbing with `analyze` via a private `_request_structured_json` helper).
The one exception: `paper_count` is overwritten with the real `len(analyses)`
after parsing, rather than trusted from the model, since that's ground truth
we already have.

**Feeding structured data back into the model, not raw text.** The
comparison prompt (`prompts/paper_comparison.py`) receives each paper's
already-extracted `PaperAnalysis` fields as JSON, not the original
abstracts — this keeps the comparison call cheap (no re-processing raw
text) and lets the model focus purely on cross-paper synthesis.

## Docker

Each service has its own `Dockerfile`; the root `docker-compose.yml` runs
both for local development with source mounted as a volume (live reload).
The frontend image currently just runs `npm run dev` — a production
multi-stage build (static `vite build` output served by nginx) is
intentionally deferred to `docker/` until deployment is actually
implemented, per project scope. A Postgres service is noted but commented
out in `docker-compose.yml` until the project needs it.

## What's deliberately not here yet

- No persistence of search results or analyses (both are live-only; nothing
  is written to the `papers` table yet — that's a separate "ingestion" concern)
- No frontend wiring for AI analysis or comparison yet (see above)
- No automatic server-side trigger that counts analyses over time and fires
  the comparison on its own — the caller supplies the batch (see above)
- No auth/user accounts
- No Alembic migrations (SQLite schema is created ad hoc during this
  scaffolding phase; Alembic should be introduced alongside the first real
  migration, once the schema stabilizes)
- No production Docker/deployment pipeline

These are out of scope for this skeleton by design.
