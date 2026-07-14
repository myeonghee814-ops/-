# BLIP - Battery Literature Intelligence Platform

An AI literature assistant built specifically for battery researchers, not a
generic paper summarizer. Given a keyword - in Korean, English, or mixed
scientific shorthand (`"NCA 전해액 첨가제"`, `"LHCE"`, `"LiFSI"`) - BLIP expands
it into the right English scientific search terms, searches the literature,
and returns the 10 most *relevant* recent papers, ranked by an AI acting like
a senior battery researcher rather than by keyword match alone. For every
paper it answers, in natural Korean, **"왜 이 논문을 읽어야 하는가?"**

## Vision

**BLIP is not a web service.** The end product is a Windows desktop
application (a packaged `.exe`), for Korean battery researchers running it
locally. Web deployment is explicitly not the priority.

- The priority is search/recommendation quality, not UI polish, and not
  infrastructure.
- The architecture stays **React (frontend) + FastAPI (backend) + SQLite**,
  the same as Sprint 1 - both are trivial to package into a desktop app
  later (Electron shell wrapping the built React app + the FastAPI backend
  running as a local sidecar process on `localhost`). Nothing in this
  codebase should assume a browser-hosted, multi-tenant, or cloud-deployed
  environment:
  - no authentication / user accounts
  - no payments
  - no Docker, no cloud services, no external infra beyond PubMed + OpenAI
  - the frontend only ever talks to a `localhost` backend URL
    (`VITE_API_BASE_URL`), which is exactly how it will reach the FastAPI
    sidecar once wrapped in Electron
  - SQLite is a single local file - it needs no server, matching how a
    desktop app persists data
- Electron packaging itself, PDF upload, Excel export, and paper comparison
  are **not implemented yet** - the architecture is simply kept compatible
  with adding them later (see "Sprint 3 candidates" below).

## Language policy

**All UI is Korean.** Every button, menu, label, loading state, and error
message the user sees is Korean. The only text that stays in its original
language is raw bibliographic data taken directly from the source paper:
**paper title, journal name, DOI, and author names remain in English**
(translating those would misrepresent the source). Everything the AI
generates as an explanation - relevance reasoning, experimental conditions,
performance summary, innovation, advantages, limitations - is written in
natural Korean.

## Search: Korean and English, transparently

Users should never need to know the right English scientific term. A search
for `"실리콘 음극 SEI"` or `"TEMPO"` or `"NCA 전해액 첨가제"` all work: before
querying PubMed, an AI query-expansion step (`ai_service.expand_search_query`)
translates/expands whatever the user typed - Korean, English, or a bare
abbreviation - into an effective English PubMed search query, using standard
scientific terminology and synonyms. The expanded query is stored alongside
the search (`SearchQuery.expanded_query`) for transparency and debugging.

## Mission

Reduce literature search time by more than 70%, by prioritizing search
quality over UI polish.

## Sprint 1 + Sprint 2 scope (this codebase)

1. Home page with keyword search (Korean or English)
2. Bilingual query expansion before the PubMed search
3. Top-10 ranked paper list, Korean UI and Korean AI recommendations
4. Paper detail page (battery snapshot, experimental conditions, performance,
   innovation, advantages, limitations, abstract, metadata), Korean UI and
   Korean AI analysis

No comparison, no PDF upload, no Excel export, no auth, no deployment, no
Electron packaging yet - by design, per the MVP scope. See "Sprint 3
candidates" for what's intentionally deferred.

> Note: `ElectrolyteMockScreenerApp.jsx`, `mock_electrolyte_demo_data.py`, and
> `pubmed_electrolyte_scraper.py` at the repo root are earlier prototypes and
> are not part of this application.

## Project structure

```
backend/                   FastAPI app
  app/
    core/config.py         Settings loaded from environment/.env
    db/
      database.py          SQLAlchemy engine/session, get_db dependency
      models.py             Paper, SearchQuery (keyword + expanded_query), SearchResult tables
    schemas/                Pydantic request/response models
    services/
      pubmed_service.py     Stage 2: PubMed E-utilities search + fetch
      ai_service.py         Stage 1, 3 & 4: OpenAI bilingual query expansion,
                             relevance re-ranking (Korean reasoning), and
                             battery metadata/analysis extraction (Korean)
      search_pipeline.py     Orchestrates the full pipeline and persists results
    api/
      routes_search.py       POST /api/search, GET /api/search/{id}
      routes_papers.py       GET /api/results/{id}
      converters.py           DB row -> API schema mapping
    main.py                  FastAPI app, CORS, DB init on startup
  requirements.txt
  .env.example

frontend/                  React + TypeScript (Vite) - all UI text in Korean
  src/
    api/                    Fetch client + shared TS types (mirrors backend schemas)
    components/             SearchBar, PaperCard, BatterySnapshotView, RelevanceBadge, Loading, ErrorMessage
    pages/                  HomePage, SearchResultsPage, PaperDetailPage
    styles/global.css       Single global stylesheet (no CSS framework at MVP stage)
  package.json
  .env.example
```

### Why each technology

- **FastAPI (backend)** - async-native, so the pipeline's I/O-bound stages
  (PubMed HTTP calls, OpenAI calls) run without blocking; free OpenAPI docs
  at `/docs` for a fast frontend/backend contract during MVP iteration. Runs
  identically today (as a local process you start yourself) and later as an
  Electron sidecar process - no code changes needed for that transition.
- **SQLite + SQLAlchemy (database)** - zero-ops, file-based, nothing to run
  or provision locally, and it's exactly the kind of embedded storage a
  desktop app should use (no separate DB server). It doubles as an
  **AI-call cache**: battery metadata extraction is stored per paper (keyed
  by PubMed ID) in the `papers` table, so a paper that resurfaces in a later
  search reuses its extraction instead of paying for another OpenAI call.
  Only the relevance score and Korean "추천 이유" are search-specific
  (`search_results` table).
- **React + TypeScript + Vite (frontend)** - Vite gives fast local dev with
  minimal config, and its static production build (`vite build`) is exactly
  the artifact an Electron `BrowserWindow` loads - no framework change is
  needed to go from "browser at localhost:5173" to "Electron window loading
  the built `dist/`". TypeScript types are hand-mirrored from the backend
  Pydantic schemas (`frontend/src/api/types.ts`) to keep the contract
  explicit without adding codegen tooling at MVP stage.
- **OpenAI API (AI)** - one call expands the user's Korean/English/shorthand
  keyword into an English PubMed query, one batched call re-ranks *all*
  PubMed candidates together (so the model compares them against each other,
  not just against the keyword in isolation) and writes the Korean "why read
  this" reasoning, and one call per top-10 paper extracts structured battery
  metadata + Korean research analysis.

## Search pipeline

```
Keyword (Korean, English, or shorthand e.g. "LiFSI", "TEMPO")
  -> AI query expansion (ai_service.expand_search_query): one OpenAI call
     translates/expands the keyword into an effective English PubMed query
  -> PubMed search (pubmed_service): esearch + efetch on the expanded query,
     ~40 candidates, sorted by PubMed's own relevance
  -> AI re-ranking (ai_service.rerank_candidates): one OpenAI call scores
     every candidate 0-100 on chemistry/electrolyte/cell-type/experimental
     similarity, application relevance, recency, and journal quality -
     plus a concrete Korean "왜 이 논문을 읽어야 하는가" note
  -> Battery metadata extraction (ai_service.extract_battery_analysis):
     for the top 10, one OpenAI call each extracts cathode/anode/
     electrolyte/voltage window/cell type plus Korean experimental
     conditions, performance summary, innovation, advantages, limitations
  -> Persisted to SQLite (SearchQuery + SearchResult + Paper) and returned
```

## Running locally

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in OPENAI_API_KEY and NCBI_EMAIL
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env   # defaults to http://localhost:8000
npm run dev
```

Open http://localhost:5173.

### Configuration

| Variable | Where | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | backend/.env | Required for query expansion, re-ranking, and extraction |
| `OPENAI_MODEL` | backend/.env | Defaults to `gpt-4o-mini` |
| `NCBI_EMAIL` | backend/.env | Required by NCBI E-utilities usage policy |
| `NCBI_API_KEY` | backend/.env | Optional, raises PubMed rate limits |
| `PUBMED_CANDIDATE_COUNT` | backend/.env | How many PubMed candidates feed the re-ranker (default 40) |
| `TOP_N_RESULTS` | backend/.env | How many ranked results are returned (default 10) |
| `VITE_API_BASE_URL` | frontend/.env | Backend URL (default `http://localhost:8000`) - this is the same URL shape the app will use once wrapped in Electron and talking to a local sidecar |

A search request runs the full pipeline synchronously and can take
10-60 seconds depending on OpenAI latency and how many of the top-10 papers
still need metadata extraction - this is intentional for MVP simplicity
(no background job queue).

## Sprint 3 candidates (not implemented - awaiting approval)

Out of scope for now, deferred by design; the architecture above is meant
to accommodate these without rework:

- Electron packaging (wrap the Vite build + run FastAPI as a local sidecar)
- Excel export of search results
- Paper comparison view (side-by-side)
- PDF upload / full-text ingestion
- A settings page (e.g. editable API key, model choice) instead of `.env`
