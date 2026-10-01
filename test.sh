#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
run_backend() { .venv/bin/python -m pytest backend/tests -q; }
run_frontend() { (cd frontend && npm test && npm run typecheck); }
run_e2e() { (cd frontend && npm run e2e); }
case "${1:-all}" in
  backend) run_backend ;;
  frontend) run_frontend ;;
  e2e) run_e2e ;;
  all) run_backend; run_frontend; run_e2e ;;
  *) echo 'Usage: ./test.sh [backend|frontend|e2e|all]' >&2; exit 2 ;;
esac
