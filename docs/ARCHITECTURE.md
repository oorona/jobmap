# Architecture

## Services

```
           internet (Traefik, HTTPS)
                  │
          ┌───────▼────────┐
          │  jev-frontend  │  Next.js: pages, /api/* proxy, CSP, robots/sitemap
          └───────┬────────┘
                  │ intranet
          ┌───────▼────────┐        ┌────────────────┐
          │  jev-backend   │───────▶│ jev-embeddings │  FastEmbed on CPU (internal only)
          │    FastAPI     │        └────────────────┘
          └──┬─────────┬───┘
     dbnet   │         │ HTTPS (X-Api-Key, backend only)
   ┌─────────▼──┐   ┌──▼──────────────────────┐    TypeSafe Jev API
   │ PostgreSQL │   │ MexicoDev jobs-v1 API   │    (relevance refinement)
   │ + pgvector │   └─────────────────────────┘
   └────────────┘
```

`jev-frontend` sits on `internet` and `intranet`; `jev-backend` on `intranet` and `dbnet`; `jev-embeddings` on `intranet` only. All containers run as non-root with internal ports only.

## Ownership boundary

MexicoDev owns ingestion, validation, cleaning, classification, publication decisions, source evidence, and physical purging of jobs after two calendar months. JobMap is a consumer: read paths never classify or clean postings. Earlier HN ingestion and source-parsing modules were removed when MexicoDev took over that role.

## Backend modules (`backend/app`)

| Module | Role |
|---|---|
| `main.py` | FastAPI app and routes: `/api/catalog`, `/api/jobs/{id}`, `/api/market`, `/api/market/jobs`, `/api/search`, `/api/search/refine`, `/api/search/models`, `/api/search/vector`, `/api/search/compare`, `/api/status`, `/api/usage`, `/health` |
| `contracts.py` | Strict schema for the documented `jobs-v1` feed |
| `upstream.py` | Transport adaptation: maps MexicoDev's four 0–3 criteria to 0–1 consumer weights, preserves unknowns, labels missing multi-role titles, translates evidence quotes and advertisement-based market drilldowns |
| `feed.py` | Catalog cache: snapshot pagination with retries, atomic replacement, ETags, expiry and withdrawal removal, bounded memory; an unusable snapshot is dropped after 15 minutes of upstream failure, and a partial download never replaces published records |
| `fixtures.py` | Invented, labeled contract fixtures for development and tests |
| `retrieval.py` | Bounded lexical/alias candidate retrieval (up to 30) that ignores conversational filler |
| `intelligence.py` | Jev relevance refinement, rate/concurrency limits, session-isolated cache, spending ledger |
| `db.py` | Operational state (usage reservations, cache, limits) |
| `vector_search.py`, `embedding_models.py` | Versioned current-posting store, per-model embedding indexing, exact pgvector cosine search |
| `comparison.py` | Runs the Jev pipeline and the three embedding pipelines side by side |

Migrations live in `backend/alembic/versions` (`001_initial`, `002_vectors`).

## Frontend (`frontend`)

- `components/Explorer.tsx` orchestrates the discover view; `Graph.tsx` is the d3-force bubble map; `Filters.tsx`, `Details.tsx`, `Market.tsx`, `Comparison.tsx`, `Usage.tsx` are the other panels.
- `lib/search.ts` does immediate local matching; `lib/filters.ts` implements hard requirements and pay comparison; `lib/store.ts` keeps bookmarks, saved searches and preferences in device storage (never job descriptions); `lib/useExpiry.ts` removes jobs at their exact expiry.
- `app/api/[...path]` proxies to the backend; `app/jobs/[id]` server-renders public job pages. `robots.txt` and `sitemap.ts` block indexing in fixture mode, and `llms.txt` labels the data as invented preview jobs.

## Search refinement flow

1. Each keystroke filters locally and updates list and graph immediately.
2. After one idle second, the backend retrieves up to 30 candidates and sends their first 1,000 search-text characters to Jev (`jev-1.13.0`).
3. Candidates scoring at least 0.65 remain in the refined list and rise in the graph; unevaluated jobs drop out of the refined list, context bubbles stay at the bottom.
4. A generation/version check rejects responses for an outdated query. Editing, clearing or IME composition cancels or defers pending work.

Cache keys combine API state, normalized query, requirements, candidate evidence versions, rubric, model version and anonymous session. Cache values hold IDs and judgments only. Usage is reserved transactionally before each call; if provider billing is uncertain, the reservation is kept. Allowances: $0.75/day and $7.50/month for JobMap, $0.25/day and $2.50/month for MexicoDev ingestion, with no borrowing between them. `/api/usage` returns aggregate totals without queries, credentials or call identifiers.

## Embedding index

- Models: `sentence-transformers/all-MiniLM-L6-v2`, `BAAI/bge-small-en-v1.5`, `snowflake/snowflake-arctic-embed-s` (384 dimensions), FastEmbed 0.8.1 on CPU.
- Postings are chunked at 600 characters with 100 overlap, encoded with each model's passage encoding, and mean-pooled with normalization. Queries use the query encoding.
- `jev.search_jobs` holds current postings (description text bounded to 50,000 characters); `jev.job_embeddings` holds one vector per posting per model. Deletes cascade to vectors.
- A background synchronizer embeds only new or changed content (by content hash and encoding version), in batches of 8. Withdrawals are purged on each successful fresh snapshot and expired rows every 30 seconds.
- Search is an exact cosine scan, with no ANN index. Requests validate current versions, so an old index cannot silently serve obsolete results. Index failures are visible and retried; Jev search remains available.

## Comparison method

The Compare tab is end-to-end, not like-for-like: the Jev pipeline judges up to 30 lexical candidates, while embeddings scan all eligible indexed postings. The UI discloses this. Queries run concurrently against preloaded models and bypass result caches. Timings include query encoding plus SQL, or retrieval plus Jev API latency; indexing and catalog loading are excluded.

## Evaluation package (`backend/evaluation`)

`dataset.py` (synthetic labeled set and live query list), `runner.py` (isolated runs), `bm25.py` (lexical baseline), `metrics.py`, `judge.py` (LLM judge with prompt caching and cost accounting), `report.py` and `blind.html` (reports and blind grading workbench). Details are in its [README](../backend/evaluation/README.md).
