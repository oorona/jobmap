# JobMap

JobMap is a dark, graph-first job discovery and market explorer for software jobs. It consumes MexicoDev's cleaned jobs API (`jobs-v1`), which ingests and normalizes "Who is hiring" style postings, and turns the current catalog into an interactive bubble map, a searchable list, and a monthly skills market view. It is a pure consumer: it never classifies or cleans source postings itself, and it keeps no historical job archive.

The project is also a testbed for comparing search methods on real job descriptions: a typed LLM relevance judge (TypeSafe's Jev model) against three local sentence-embedding models, side by side, with timings, costs and human relevance labels.

- Installation, configuration and deployment: [docs/INSTALLATION.md](docs/INSTALLATION.md)
- Components, data flow and internals: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Test and deployment evidence: [docs/verification.md](docs/verification.md)

## Features

- **Discovery graph.** Every current posting is a bubble with a stable position. A D3 collision layout gives a one-time rise/settle animation, then stays still. Bubbles can be dragged, selected with the keyboard or touch, and show contextual relationships between jobs. Reduced-motion preferences are respected. A color guide explains skill groups, selection, "potential jewels" and relationships, and colors are also named in focus/hover text.
- **Immediate local search** with a synchronized list, posting-age filters, hard remote/country requirements, a clarification view, and evidence-backed preference indicators. Conversational filler ("I want a job with...") is ignored.
- **Filters** for location/country, remote/hybrid/on-site, salary disclosed, and minimum pay. Pay comparisons keep currency and period separate and use the published lower bound. Unknown values never satisfy an active filter.
- **Job details** in a drawer and on server-rendered public job pages: application links, source evidence quotes, explicit unknowns (visa sponsorship, work authorization, time zones, ...) and availability caveats.
- **Device-local bookmarks, saved searches and preferences.** Job descriptions are never written to browser storage.
- **Skills market timeline.** Monthly counts and percentages per skill, completed-month or elapsed-window comparisons, selectable months, second-skill intersections, and drilldown to the source postings.
- **Live feed handling.** Schema validation, bounded payloads, snapshot pagination with retries, atomic replacement, stale-data handling, prompt removal of withdrawn jobs, and exact expiry. A partial download never replaces published records.
- **Usage & costs panel** showing UTC daily/monthly recorded charges, reservations, remaining allowance and refinement availability.

## AI and search

**LLM relevance refinement (Jev).** Typing shows local matches immediately. After one idle second, up to 30 retrieved candidates are sent to TypeSafe's Jev model (pinned `jev-1.13.0`), which returns a typed relevance probability per job. Only candidates at 0.65 or above stay in the refined list and rise in the graph. Generation/version checks make sure a stale response can never replace the current query; editing, clearing or IME composition cancel or defer pending work. If the budget runs out or the provider fails, the local results stay usable with an explicit status.

**Cost control.** Inference spending is capped at $0.75/day and $7.50/month UTC for this consumer, out of a combined product allowance of $1/day and $10/month shared with MexicoDev ingestion. Hovering, dragging, opening details or changing preference weights never triggers inference. Session/IP rate limits, concurrency limits, session-isolated caches (which hold IDs and judgments, never source text) and transactional usage reservations protect the public endpoint.

**Embedding search.** A "Search with" selector switches between the Jev pipeline and three independent cosine-search models, served locally on CPU with FastEmbed: `sentence-transformers/all-MiniLM-L6-v2`, `BAAI/bge-small-en-v1.5` and `snowflake/snowflake-arctic-embed-s` (384-dimensional, English). Postings are chunked (600 characters, 100 overlap) with each model's own query/passage encoding and stored in PostgreSQL with pgvector. Search is an exact cosine scan with no ANN index, so approximation never confounds the comparison.

**Compare tab.** Runs all four methods on the same query, filters and catalog snapshot, showing each method's results, scores, latency and failures. Users label results as relevant or not; labels are shared per job across columns and precision is computed only over judged results. Everything (rankings up to 30 per method, scores, timings, cutoffs, labels) can be exported. The UI is explicit that embedding scores are cosine similarities, not probabilities, and that a result count is not an accuracy score.

**Evaluation suite.** A reusable offline benchmark runs the same methods against a fully labeled synthetic set (72 postings, 48 queries, held-out split with cutoffs calibrated on development queries) or against the live corpus. It reports precision@5, nDCG@10, recall@10, latency percentiles, macro F1 with correct abstention on no-match queries, paired bootstrap intervals, and API cost. Real-job relevance can be graded blind by humans or by an independent LLM judge that records a grade, explanation and evidence per query/job pair, with token usage and estimated cost. Reports keep provisional LLM judgments separate from human labels.

## Tech stack

- **Frontend:** Next.js 16 (App Router, TypeScript), d3-force for the graph layout, server-rendered job pages, per-request CSP and security headers, Vitest and Playwright (desktop and mobile Chromium).
- **Backend:** Python 3.13, FastAPI, async SQLAlchemy (asyncpg) with Alembic migrations, PostgreSQL 18 with pgvector, pytest.
- **Embeddings service:** FastEmbed 0.8.1 on CPU, internal-only HTTP service.
- **AI:** TypeSafe Jev for typed relevance judgments; an LLM judge for offline evaluation.
- **Deployment:** Docker Compose with hardened non-root services, Docker secrets, and Traefik routing.
