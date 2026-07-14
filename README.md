# BLIP - Battery Literature Intelligence Platform

A search engine built for battery researchers, not a generic paper summarizer.
Given a keyword (e.g. `"NCA electrolyte additive"`), BLIP returns the 10 most
*relevant* recent papers - ranked by an AI acting like a senior battery
researcher, not by keyword match alone - and explains, for each one, **why a
battery researcher should read it**.

## Mission

Reduce literature search time by more than 70%, by prioritizing search
quality over UI polish.

## Sprint 1 scope (this codebase)

1. Home page with keyword search
2. Top-10 ranked paper list
3. Paper detail page (battery snapshot, experimental conditions, performance,
   innovation, advantages, limitations, abstract, metadata)

No comparison, no PDF upload, no Excel export, no auth, no deployment - by
design, per the MVP scope.

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
      models.py             Paper, SearchQuery, SearchResult tables
    schemas/                Pydantic request/response models
    services/
      pubmed_service.py     Stage 1: PubMed E-utilities search + fetch
      ai_service.py         Stage 2 & 3: OpenAI re-ranking + battery
                             metadata/analysis extraction
      search_pipeline.py     Orchestrates the full pipeline and persists results
    api/
      routes_search.py       POST /api/search, GET /api/search/{id}
      routes_papers.py       GET /api/results/{id}
      converters.py           DB row -> API schema mapping
    main.py                  FastAPI app, CORS, DB init on startup
  requirements.txt
  .env.example

frontend/                  React + TypeScript (Vite)
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
  at `/docs` for a fast frontend/backend contract during MVP iteration.
- **SQLite + SQLAlchemy (database)** - zero-ops, file-based, nothing to run
  or provision locally. It doubles as an **AI-call cache**: battery metadata
  extraction is stored per paper (keyed by PubMed ID) in the `papers` table,
  so a paper that resurfaces in a later search reuses its extraction instead
  of paying for another OpenAI call. Only the relevance score and
  "why selected" reasoning are search-specific (`search_results` table).
- **React + TypeScript + Vite (frontend)** - Vite gives fast local dev with
  minimal config; TypeScript types are hand-mirrored from the backend
  Pydantic schemas (`frontend/src/api/types.ts`) to keep the contract
  explicit without adding codegen tooling at MVP stage.
- **OpenAI API (AI)** - one batched call re-ranks *all* PubMed candidates
  together (so the model compares them against each other, not just against
  the keyword in isolation), and one call per top-10 paper extracts
  structured battery metadata + research analysis.

## Search pipeline

```
Keyword
  -> PubMed search (pubmed_service): esearch + efetch, ~40 candidates,
     sorted by PubMed's own relevance
  -> AI re-ranking (ai_service.rerank_candidates): one OpenAI call scores
     every candidate 0-100 on chemistry/electrolyte/cell-type/experimental
     similarity, application relevance, recency, and journal quality -
     plus a concrete "why should a battery researcher read this" note
  -> Battery metadata extraction (ai_service.extract_battery_analysis):
     for the top 10, one OpenAI call each extracts cathode/anode/
     electrolyte/voltage window/cell type plus experimental conditions,
     performance summary, innovation, advantages, limitations
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
| `OPENAI_API_KEY` | backend/.env | Required for re-ranking and extraction |
| `OPENAI_MODEL` | backend/.env | Defaults to `gpt-4o-mini` |
| `NCBI_EMAIL` | backend/.env | Required by NCBI E-utilities usage policy |
| `NCBI_API_KEY` | backend/.env | Optional, raises PubMed rate limits |
| `PUBMED_CANDIDATE_COUNT` | backend/.env | How many PubMed candidates feed the re-ranker (default 40) |
| `TOP_N_RESULTS` | backend/.env | How many ranked results are returned (default 10) |
| `VITE_API_BASE_URL` | frontend/.env | Backend URL (default `http://localhost:8000`) |

A search request runs the full pipeline synchronously and can take
10-60 seconds depending on OpenAI latency and how many of the top-10 papers
still need metadata extraction - this is intentional for MVP simplicity
(no background job queue).
