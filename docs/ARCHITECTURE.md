# BLIP Architecture

This document explains the design decisions behind the project. BLIP is a
literature analysis tool for battery electrolyte researchers, not a
generic paper search engine — every feature exists to reduce reading time,
increase scientific accuracy, make papers easy to compare, extract
experimental conditions into structured data, or present information more
cleanly. Anything that doesn't serve one of those five goals doesn't get
built, even if it would be an easy addition.

Literature search (`GET /api/search`), AI paper analysis
(`POST /api/v1/analyze`), the AI comparison engine (`POST /api/v1/compare`),
Excel export (`POST /api/v1/export`), and a dedicated paper comparison page
are implemented, and the project has a production-shaped deployment path:
multi-stage Docker images, a Postgres + Alembic migration path, structured
logging, request tracing, Prometheus metrics, and authentication
scaffolding (see the relevant sections below). Persisting/organizing
papers and real user authentication are not implemented — this describes
the scaffolding those remaining features will be built on.

## Layering (backend)

```
api/               HTTP concerns only: routing, request/response models, status codes
services/          Business logic, orchestration
services/external/ Provider-specific API clients (Semantic Scholar, OpenAlex, OpenAI)
models/            SQLAlchemy ORM models — the persistence shape
schemas/           Pydantic models — the API contract shape
database/          Engine/session lifecycle, declarative base
core/              Cross-cutting concerns: settings, logging, middleware,
                   metrics, caching, shared HTTP clients, security helpers
alembic/           Database migrations (see "Async SQLAlchemy..." below)
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

## Async SQLAlchemy + SQLite now, Postgres via Alembic in production

`DATABASE_URL` is the only thing that changes between environments
(`sqlite+aiosqlite:///./blip.db` locally, `postgresql+asyncpg://...` in
production — `asyncpg` is already in `requirements.txt`) because the
codebase only ever talks to SQLAlchemy's async engine/session API, never
to a driver directly. Async is used from the start (`AsyncSession`,
`async def` routes) so adopting Postgres is a config change, not a rewrite
of every endpoint. `docker-compose.prod.yml` runs a real `postgres:16-alpine`
service; the dev compose file still uses SQLite, and both are exercised by
the same application code unchanged.

**Alembic** (`backend/alembic/`) manages schema changes for whichever
database `DATABASE_URL` points at. `alembic/env.py` is customized in two
ways from the generated template: it pulls the connection URL from the
app's own `Settings` (`get_settings().DATABASE_URL`) instead of a
hardcoded value in `alembic.ini`, so migrations always run against
whatever database the app itself is configured for; and it imports every
model module (`models/paper.py`, `models/user.py`) so `Base.metadata` is
fully populated before `--autogenerate` compares against it. The initial
migration (`alembic/versions/..._initial_schema.py`) was generated via
`alembic revision --autogenerate` against a real (empty) SQLite database,
then verified: `alembic upgrade head` creates both tables, `alembic
downgrade base` cleanly drops them, and `alembic check` reports zero drift
against the current models. (Verified against SQLite in this environment;
a live Postgres container wasn't reachable here — no Docker daemon — but
nothing in the migration or `DATABASE_URL` handling is SQLite-specific.)

In production, `backend/entrypoint.sh` runs `alembic upgrade head` before
starting the server (see "Docker" below) — fine for a single instance, but
if this ever scales to multiple replicas deploying at once, that step
should move to a separate one-off job so replicas don't race to migrate
concurrently.

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

## Logging, request tracing, and metrics

`core/logging.py` configures the root logger once, at import time in
`main.py`, via `logging.config.dictConfig`. Every module then just calls
`logging.getLogger(__name__)` and inherits consistent formatting.
`LOG_FORMAT` switches between two formatters, both driven by the same env
var mechanism as everything else in `core/config.py`:

- `text` (default): human-readable, for local development.
- `json`: one JSON object per line (`core/logging.py::JsonFormatter`),
  because production log aggregators (CloudWatch, Datadog, ELK, ...) parse
  structured logs far more reliably than formatted text. Any `extra={...}`
  fields a caller attaches (e.g. `request_id`) are included automatically.

`core/middleware.py::RequestContextMiddleware` wraps every request: it
assigns a request ID (reusing an inbound `X-Request-ID` header if a proxy
already set one, so the ID survives a hop), logs method/path/status/duration
for every request tagged with that ID, and echoes it back as a response
header. This is a structured, app-level complement to uvicorn/gunicorn's
own access logs — the shared ID is what lets a specific user-reported
error be found in server logs.

The same middleware records two Prometheus metrics (`core/metrics.py`):
`http_requests_total` (counter, labeled by method/path/status) and
`http_request_duration_seconds` (histogram, labeled by method/path).
Labels use the *matched route's path template* (e.g. `/paper/{id}`) rather
than the raw resolved URL, specifically so a future endpoint with a path
parameter can't explode metric cardinality by generating one label per
distinct ID ever requested.

## Monitoring: `/metrics` and `/api/v1/health/ready`

`/metrics` is a plain ASGI app (`prometheus_client.make_asgi_app()`)
mounted directly in `main.py`, not a FastAPI route. This project initially
tried the higher-level `prometheus-fastapi-instrumentator` wrapper package,
but its latest release requires Starlette 1.x while this project's FastAPI
pin requires Starlette <0.47 — a real, current dependency conflict, not a
hypothetical one (`pip install prometheus-fastapi-instrumentator` visibly
broke the app in this environment). `prometheus_client` itself has no such
coupling, so instrumenting manually via the middleware above sidesteps the
conflict entirely and is barely more code.

Two separate health endpoints, deliberately not merged into one:

- `GET /api/v1/health` — pure liveness. No dependencies (no DB, no
  external calls), so it can never report unhealthy for a reason outside
  the process's own control. This is what should back a container
  orchestrator's "is this process alive, or does it need a restart" check.
- `GET /api/v1/health/ready` — readiness. Runs `SELECT 1` against the
  database and returns 503 if that fails. This is what should gate
  traffic/rollout (a Kubernetes readinessProbe, a load balancer's health
  check) — an instance can be alive but not yet able to serve real
  requests (e.g. DB still starting up), and conflating the two checks
  would either restart a healthy-but-not-ready process unnecessarily or
  route traffic to an instance that can't yet serve it.

## Shared HTTP/OpenAI clients (`core/http_clients.py`)

Every external client (`services/external/*.py`) used to open a brand-new
`httpx.AsyncClient` or `AsyncOpenAI` instance — and therefore pay for a
fresh TCP/TLS handshake — on every single call. That's most costly exactly
where it matters most: the export pipeline analyzing a dozen papers
concurrently used to open a dozen separate OpenAI connections instead of
reusing a warm pool. `get_http_client()`/`get_openai_client()` are lazy
module-level singletons (connection-pooled via `httpx.Limits`), created on
first use and closed once via `aclose_all()` in `main.py`'s `lifespan` on
shutdown. This is the main "optimize the API" change in this pass, along
with `GZipMiddleware` (main.py) compressing responses over 500 bytes —
worthwhile given how large the search/analysis/comparison JSON payloads
can get.

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
  refetching) via `useMutation` for every user-triggered AI action
  (`useAnalyzePaper`, `useAnalyzePapers`, `useComparePapers`,
  `useExportPapers`) so components don't hand-roll `useEffect` + `useState`
  data fetching or loading/error flags.
- **services/** isolates the HTTP layer: if the API contract changes,
  only the relevant `*Service.ts` file changes, not every component that
  uses it. `services/apiError.ts::getErrorMessage` centralizes pulling a
  readable message out of a FastAPI `{"detail": "..."}` error response, so
  every mutation's error state can render something better than "Request
  failed" with one shared helper.
- **AG Grid** powers both the search results table and the paper
  comparison table, including multi-row selection
  (`rowSelection={{ mode: 'multiRow', checkboxes: true }}`) on the search
  page used to pick papers for "Compare Selected" and "Export Selected."
- **types/analysis.ts and types/comparison.ts** mirror
  `schemas/analysis.py`/`schemas/comparison.py` field-for-field, the same
  convention `types/paper.ts` already used for `schemas/search.py`. The
  frontend didn't consume `/analyze` or `/compare` JSON directly before
  this pass (only the export pipeline called them, server-side, returning
  an opaque file) — these are the first types for that.
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
set of fields the frontend's paper detail page and search results table show
(battery_system, electrolyte, salt, solvent, additive, cathode, anode,
separator, cell type, voltage window, temperature, formation protocol, cycle
condition, rate capability, main findings, innovation, advantages,
limitations, future work), plus title/authors/journal for cross-checking
against the source paper.

**`battery_system`** (Li-ion, Li-metal, Na-ion, solid-state, ...) was added
specifically for the search results table's "Battery System" column —
letting a researcher scan chemistry class across many results without
opening any of them is a direct "reduce reading time" win. The search
table's "Main Contribution" column deliberately reuses the existing
`innovation` field (relabeled client-side) rather than adding a duplicate
field with the same meaning — see "Redesign: search results and paper
detail" below.

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

**Now wired to the frontend, two ways.** `frontend/src/hooks/useAnalyzePaper.ts`
backs the paper detail page's "Analyze This Paper" button (single paper, on
demand). `frontend/src/hooks/useAnalyzePapers.ts`
(`services/analysisService.ts::analyzePapers`) calls this endpoint
concurrently for many papers at once via `Promise.allSettled`, tolerating
individual failures (no abstract, a transient error) rather than letting one
bad paper fail the batch — the client-side mirror of what
`services/export_service.py::_analyze_all` already did server-side. This
batch helper backs both the search page's "Analyze Results" button and the
"Compare Selected" flow below. Analysis was deliberately kept **out** of the
search endpoint itself — running AI analysis on every search result
automatically (up to 100 papers per the existing limit selector) would make
search slow and expensive, undermining "reduce reading time"; it's an
explicit, bounded, opt-in action instead.

## AI comparison engine (`POST /api/v1/compare`)

Input: a batch of already-analyzed papers — `schemas/comparison.py::ComparisonRequest`
takes `{"analyses": [PaperAnalysis, ...]}`, i.e. output of `/api/v1/analyze`
called once per paper. Output: `ComparisonResult` — common experimental
conditions, differences, frequently used electrolytes/additives, most
common cathode/anode, research trend, research gap, potential future
direction, and a `comparison_table` (one row per input paper: title,
electrolyte, salt, additive, cathode, anode, separator, cell type, voltage
window, temperature, cycle condition, main_finding, advantages,
limitations) for scanning papers side by side without opening any of them.

**Comparison table columns beyond the original 8.** `ComparisonTableRow`
originally only had title/electrolyte/cathode/anode/separator/cell_type/
voltage_window/temperature. The dedicated Paper Comparison page's spec
asked for salt, additives, cycle condition, main finding, advantages, and
limitations too — all extended onto the existing row shape (additive,
nullable fields) rather than a new schema, and all sourced from data the
model already had access to (each paper's `PaperAnalysis`) — no new
extraction concept, just more of what was already being extracted made
visible in the table. `separator`/`cell_type` were kept even though the
new spec's column list didn't name them, since removing working, useful
columns wasn't asked for; the *on-screen* comparison table
(`frontend/src/pages/ComparisonPage.tsx`) shows exactly the requested
column set, while the Excel Comparison sheet keeps the superset — both are
free from the same underlying data, no duplicated logic.

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

## Excel export (`POST /api/v1/export`)

Input: `schemas/export.py::ExportRequest` — the papers the user selected in
the search results grid (`{"papers": [PaperResult, ...]}`). Output: a
`.xlsx` file (`StreamingResponse`, not JSON) with four sheets: **Paper
Summary** (bibliographic metadata plus Battery System/Main Contribution,
matching the search results table's columns), **Experimental Conditions**,
**AI Summary** (innovation/findings/advantages/limitations/future work), and
**Comparison** (cross-paper synthesis plus a per-paper side-by-side table,
now including salt/additive/cycle condition/main finding/advantages/
limitations alongside the original columns).

**Export analyzes independently of the comparison page, and re-analyzes on
every call.** `services/export_service.py` analyzes every selected paper
concurrently (`asyncio.gather`, using each paper's title+abstract already
in hand from search — no re-fetching), then runs the comparison engine over
whatever analyses succeeded, provided there are at least
`COMPARISON_MIN_PAPERS`. If a user compares papers on the Paper Comparison
page and then clicks "Export to Excel" there, the papers get analyzed a
second time (once for the on-screen comparison, once inside export) rather
than the first result being reused — accepted as a reasonable simplicity/
cost tradeoff for now (no new endpoint, no `ExportRequest` schema change to
accept pre-computed analyses) rather than over-engineering a cache for a
usage pattern that may not be common; worth revisiting if AI cost/latency
on that path becomes a real problem.

**An export should basically never hard-fail.** The Summary Table sheet
only needs data already in hand (no AI), so it always succeeds. If AI
analysis fails for a paper (no `OPENAI_API_KEY`, a rate limit, a paper with
no abstract, etc.), that paper's rows in the Experimental Conditions/AI
Summary sheets just say "Not analyzed" rather than aborting the whole
export — same "degrade gracefully, don't fabricate" principle as the paper
detail page and `/analyze` itself. Comparison degrades the same way: below
the minimum batch size (or on a provider failure), the Comparison sheet
shows an explanatory note instead of fake data.

**openpyxl usage is split from AI orchestration.** `services/excel_export_service.py`
is synchronous and network-free — it only takes already-fetched
papers/analyses/a comparison (or `None`) and returns workbook bytes. It
never calls `analyze_paper` or `compare_papers` itself, which makes it
fully unit-testable (parse the output with `openpyxl.load_workbook` and
assert on sheet names, header styling, frozen panes, column widths)
without mocking any network boundary. `services/export_service.py` is the
only async piece, and its only job is gathering the data this module needs.

**Formatting choices**, applied consistently across sheets: a dark header
row (`fill`+bold white `font`) frozen via `freeze_panes`, thin borders on
every data cell, alternating row banding for readability, and column widths
computed from actual cell content (capped so a full abstract or a joined
bullet list can't blow out a column to an unusable width). The Comparison
sheet is laid out as a short report (labeled facts, bulleted lists) followed
by its own per-paper table — `freeze_panes` is set below *that* table's
header rather than at row 1, since that's the part of the sheet actually
long enough to need it.

## Paper Comparison page (`frontend/src/pages/ComparisonPage.tsx`)

New page, reachable from the search page's "Compare Selected" button —
not a persistent nav link, since there's nothing to show without a prior
selection (same reasoning as `/paper/:id`: no persistence yet, so state
travels via `navigate(path, { state })`, and opening the route directly
shows a graceful "select papers on the search page" message instead of an
error).

**No new backend endpoints.** `frontend/src/hooks/useComparePapers.ts`
orchestrates the existing `/analyze` (batched, client-side) and `/compare`
endpoints entirely from the browser: analyze every selected paper, keep
only the ones that succeeded, call `/compare` with those. The resulting
`{ papers, analyses, comparison }` travels to the comparison page via
router state, so the page renders immediately with no further fetch. Its
"Export to Excel" button reuses `useExportPapers` with the same `papers`
list — see the Excel export section above for the cost tradeoff that
implies.

## Redesign: search results and paper detail

BLIP's UI pivoted from generic literature search to a battery-research
tool this pass. Two things worth calling out because they involved real
interpretation of an ambiguous or overlapping spec, not just following
explicit instructions:

**Search results table dropped DOI/Abstract Preview for Battery System/
Electrolyte/Main Contribution.** The three AI-derived columns are populated
by an opt-in "Analyze Results" button (`useAnalyzePapers`, batching
`/analyze` calls for whatever's currently loaded), not automatically on
search — see the AI paper analysis section above for why. Cells show "—"
until analyzed, same convention used everywhere else in the app for
missing AI data. "Main Contribution" reuses `PaperAnalysis.innovation`
(relabeled client-side) rather than a new field with the same meaning.
Row-level analysis results are keyed by a row id derived from DOI (stable)
or array index (only unique *within one result set*) — `analysisByRowId`
is explicitly cleared on every new search submission, otherwise a new
paper landing on the same index as a previous search's paper could
silently inherit that old paper's analysis.

**Paper detail page: one "Experimental Conditions" card, not four.** The
section list named `Experimental Conditions`, `Electrolyte Composition`,
`Cell Configuration`, and `Electrochemical Evaluation` as apparently
separate sections, but `PaperAnalysis` has no narrative text per sub-topic
— only the same flat fields a dedicated "Experimental Condition Card" spec
(elsewhere in the same request) described as one compact, <30-second-scan
card. Four cards would have meant four cards repeating subsets of the same
13 fields, working against "reduce reading time" and "clean interface."
Resolved as one `Experimental Conditions` card with three internal
subheadings (`ExperimentalGroup` components for Electrolyte Composition /
Cell Configuration / Electrochemical Evaluation) — every section name from
the spec is present, but as organization within one card rather than four
separate ones. The `Keywords` card (previously a permanent placeholder,
since no keyword-extraction feature exists) was dropped since the new
section list doesn't include it.

The detail page also moved from a two-column (paper info / "Quick
Summary" sidebar) layout to a single-column stack of cards — the new spec
describes a flat list of sections rather than a two-column split, and a
single column reads more like the "clean, intuitive... suitable for
researchers working every day" tool described than a dashboard-style
split does.

## Authentication placeholders (`core/security.py`, `models/user.py`) — no login yet

Nothing in the app requires a caller to be authenticated. No route depends
on a user; no signup/login flow exists. What does exist is the scaffolding
a real auth flow will need, written and tested ahead of time rather than
improvised later under pressure:

- **`models/user.py`** — a `User` table (email, hashed_password, is_active,
  is_superuser). Structural only; nothing writes to it.
- **`schemas/user.py`** — `UserCreate`/`UserRead` placeholder schemas, not
  exposed by any endpoint. `UserRead` deliberately excludes
  `hashed_password` so it can never leave the persistence layer even by
  accident once it is wired up.
- **`core/security.py`** — password hashing (`hash_password`/
  `verify_password`) and JWT helpers (`create_access_token`/
  `decode_access_token`). Uses `bcrypt` directly rather than `passlib`:
  `passlib` is effectively unmaintained, and its bcrypt-version-detection
  code raises against current `bcrypt` releases (it looks for a
  `bcrypt.__about__` attribute recent `bcrypt` no longer exposes) — a real
  failure hit while building this, not a hypothetical one, same story as
  the Prometheus wrapper package above.
- **`api/deps.py::get_current_user`** — an `OAuth2PasswordBearer`-based
  dependency, pointed at the `/auth/token` stub below. Unconditionally
  raises 501 if anything ever calls it, since there's no valid token it
  could accept yet. No route currently depends on it, so its behavior is
  inert today; wiring up a route later means adding
  `Depends(get_current_user)` and replacing the 501 with a real decode +
  DB lookup + 401-on-invalid.
- **`api/routes/auth.py`** — `POST /auth/token` also just raises 501. It
  exists so the shape of the future login endpoint (OAuth2 password grant)
  is visible in the OpenAPI schema ahead of time.
- **`SECRET_KEY`/`ALGORITHM`/`ACCESS_TOKEN_EXPIRE_MINUTES`** in
  `core/config.py` back the JWT helpers above. The default `SECRET_KEY` is
  explicitly labeled insecure-for-dev-only; `docker-compose.prod.yml`
  refuses to start without a real one set (see "Docker" below).

## Docker

One `Dockerfile` per service, each with `development` and `production`
build stages (selected via `target:` in whichever compose file is used) —
this replaced the previous dev-only Dockerfiles now that deployment is
actually being implemented.

**Backend** (`backend/Dockerfile`): `development` mirrors the previous
single-stage image (hot reload via `--reload`, runs as root, source
bind-mounted over the image by `docker-compose.yml`). `production` adds a
non-root user, serves via `gunicorn` with `uvicorn.workers.UvicornWorker`
(worker count from the `WEB_CONCURRENCY` env var, which gunicorn reads
natively — deliberately not a hardcoded `--workers` CLI flag, since an
explicit flag always wins over the env var and would defeat the point of
making it configurable per-deployment), and runs `backend/entrypoint.sh`
(applies `alembic upgrade head`, then execs the server) rather than
starting the server directly.

**Frontend** (`frontend/Dockerfile`): `development` is the previous
single-stage image (Vite dev server). `build` runs `npm run build`. `production`
copies the static output into `nginx:1.27-alpine`. No `VITE_API_BASE_URL`/
`VITE_API_ROOT_URL` build args are needed for the production image: both
already default to relative paths (`src/services/apiClient.ts`), and
`frontend/nginx.conf` reverse-proxies `/api/` to the `backend` service
internally — same-origin in both dev (via Vite's proxy) and production (via
nginx), so no production CORS configuration is needed beyond what already
existed for local dev.

**`docker-compose.yml`** (dev, unchanged in spirit): SQLite, hot reload,
now explicitly `target: development` — important, because without an
explicit target Docker builds the *last* stage defined in the Dockerfile,
which is now `production`; leaving it unspecified would have silently
broken local dev the moment the multi-stage Dockerfiles landed.

**`docker-compose.prod.yml`** (new): adds a real `postgres:16-alpine`
service (named volume, `pg_isready` healthcheck), builds both app images
with `target: production`, and only publishes the frontend's port 80 to
the host — the backend and database are reachable only over the internal
Compose network, so nginx is the sole entry point. Required secrets
(`POSTGRES_PASSWORD`, `CORS_ORIGINS`, `SECRET_KEY`) use Compose's
`${VAR:?message}` syntax, which fails immediately with a clear message
rather than silently starting with an empty/insecure value — verified via
`docker compose -f docker-compose.prod.yml config` both with and without
those variables set. These variables are resolved by Compose itself from
a root-level `.env` (see `.env.prod.example`), which is distinct from
`backend/.env`/`frontend/.env` (consumed inside the containers by the dev
setup) — worth calling out since the two are easy to conflate.

*(Both compose files were validated with `docker compose config` — this
sandbox has the Docker CLI but no running daemon, so an actual `docker
build`/`docker compose up` of these images wasn't possible here.)*

## What's deliberately not here yet

- No persistence of search results or analyses (all live-only; nothing is
  written to the `papers` table yet — that's a separate "ingestion" concern)
- No automatic server-side trigger that counts analyses over time and fires
  the comparison on its own — the caller (search page's "Compare Selected,"
  or export's selected batch) supplies the papers each time
- No caching of AI analyses — analyzing overlapping paper sets (e.g. via
  search's "Analyze Results," then later "Compare Selected," then "Export
  to Excel" on the same papers) re-analyzes shared papers rather than
  reusing prior results, so the same paper can be sent to OpenAI multiple
  times across a single session
- No keyword extraction (the previous "Keywords" placeholder card was
  removed from the paper detail page rather than kept as a permanent stub,
  since the new section spec doesn't call for it)
- No real authentication — see "Authentication placeholders" above; no
  route requires a caller to be logged in
- No TLS termination/public ingress in `docker-compose.prod.yml` — put a
  load balancer or reverse proxy in front of it that handles TLS
- No CI/CD pipeline (tests/build are run manually)
- No secrets manager integration — `docker-compose.prod.yml` takes secrets
  from a root `.env`/the shell environment, which is fine for a single
  host but not for a multi-host/team production setup
- No rate limiting on any endpoint (relevant especially for the
  AI-backed `/analyze`, `/compare`, `/export` endpoints, which cost real
  money per call)

These are out of scope for this project's current stage by design.
