# Installation

## Requirements

- Node 24 (see `.nvmrc`) and Python 3.13
- For the deployed stack: Docker Compose, a shared PostgreSQL 18 with the `vector` extension available, and a Traefik instance on the external `internet` network

## Run locally

```sh
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements-dev.txt
cd frontend
npm ci
cd ..
./scripts/dev-backend.sh
```

In another terminal:

```sh
cd frontend
INTERNAL_API_URL=http://127.0.0.1:8018 npm run dev -- --port 3018
```

Open `http://127.0.0.1:3018`. Development uses a SQLite operational ledger in `/tmp/jev-development-ledger.db`. Local fixture mode does not create the PostgreSQL embedding index. The fixture banner stays visible in local development, and public model calls are disabled by default.

## Configuration

Copy `.env.example` to `.env` (or `.env.test` for the test deployment):

| Variable | Meaning |
|---|---|
| `PROJECT_HOST` | Public hostname routed by Traefik |
| `APP_UID` / `APP_GID` | Must match the owner of the secret files on the host so the non-root containers can read them |
| `SOURCE_MODE` | `fixture` (invented, clearly labeled data) or `live` (MexicoDev API). Fixtures are never used as a fallback for live mode |
| `MEXICODEV_API_URL` | Fixed upstream URL. Never accept a request-provided upstream URL |
| `REFINEMENT_ENABLED` | Enables Jev relevance refinement |

Docker secrets, one file each with mode 600, in `secrets/` (or `secrets.test/`):

- `db_password.txt`
- `typesafe_api_key.txt`
- `mexicodev_api_key.txt` (optional consumer key, sent only by the backend as `X-Api-Key`)

Credentials never reach the frontend.

## Connect to the live MexicoDev API

1. Put the consumer API key in `secrets.test/mexicodev_api_key.txt`, then run `.venv/bin/python scripts/check-upstream.py`. It uses live mode explicitly and fails if the feed is unavailable or incompatible.
2. Confirm the live response shape, especially the market payload and source-evidence references. Review representative real jobs and refresh/withdrawal behavior.
3. Set `SOURCE_MODE=live` in `.env.test` and recreate the services. The frontend receives the same mode, so the fixture notice and `noindex` controls change together.
4. Verify catalog loading, expiry, withdrawals, ETags, pagination resets, facets, details and chart counts.

## Tests

```sh
./test.sh all        # or: backend | frontend | e2e
cd frontend && npm run build
```

Playwright owns ports 3018/8018 and runs desktop and mobile Chromium. Backend and provider tests use isolated ledgers and mocks; browser fixture mode never spends the Jev allowance. `node scripts/smoke-preview.mjs` repeats a bounded browser smoke check against the deployed preview.

## Deploy (test host)

The deployment uses the homelab `infra/scripts/deploy.sh` sync script (read it and use its dry-run before transferring). On first install run `scripts/setup_db.sh` to create the database and role. Then enable pgvector in this database only and create the model cache:

```sh
docker exec postgres psql -U postgres -d jev -v ON_ERROR_STOP=1 -c 'CREATE EXTENSION IF NOT EXISTS vector;'
mkdir -p data/embedding-models   # owned by APP_UID/APP_GID
docker compose up -d --build
```

Backend migrations run automatically at startup and create `jev.search_jobs` and `jev.job_embeddings`. Compose sets `VECTOR_SEARCH_ENABLED=true` and the internal encoder URL. Models download once into `data/embedding-models`, which is excluded from deployment sync. Initial indexing runs in the background; **Index status & comparison method** in the UI shows coverage.

Test settings live in `.env.test` and `secrets.test/`. Production secrets and hostname are intentionally unconfigured.

## Search evaluation suite

```sh
./scripts/run-search-evaluation.sh controlled 2   # labeled synthetic benchmark, 2 repeats
./scripts/run-search-evaluation.sh live 2         # same searches on the current real corpus
```

Runs use isolated temporary tables and the normal Jev spending limits, and write HTML reports, JSON/CSV metrics, raw rankings and a blind grading workbench under `artifacts/evaluation/`. See the [evaluation protocol](../backend/evaluation/README.md) for the held-out split, calibration, label import and the resumable LLM-judge command.
