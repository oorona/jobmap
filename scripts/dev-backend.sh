#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../backend"
export SOURCE_MODE=fixture
export PROJECT_HOST=localhost
export REFINEMENT_ENABLED=false
export DATABASE_URL="sqlite+aiosqlite:////tmp/jev-development-ledger.db"
exec ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8018 --no-access-log
