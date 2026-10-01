#!/usr/bin/env bash
# Run against the existing test host, in an isolated one-off backend container.
set -euo pipefail
cd "$(dirname "$0")/.."
track=${1:-controlled}
repeats=${2:-2}
case "$track" in controlled|live) ;; *) echo 'Usage: run-search-evaluation.sh {controlled|live} [1|2|3]' >&2; exit 2;; esac
case "$repeats" in 1|2|3) ;; *) echo 'Repeats must be 1, 2, or 3' >&2; exit 2;; esac
remote='projects.home.iktdts.com'
project='/home/iktdts/apps/website/jev'
ssh "$remote" "mkdir -p '$project/backend/evaluation' '$project/artifacts/evaluation'"
rsync -a --exclude='__pycache__/' backend/evaluation/ "$remote:$project/backend/evaluation/"
rsync -a backend/app/intelligence.py "$remote:$project/backend/app/intelligence.py"
run_status=0
ssh "$remote" "cd '$project' && docker compose run --rm --no-deps --entrypoint python --workdir /benchmark -v '$project/backend/app:/benchmark/app:ro' -v '$project/backend/evaluation:/benchmark/evaluation:ro' -v '$project/artifacts/evaluation:/results' jev-backend -m evaluation.runner --track '$track' --repeats '$repeats' --max-usd 0.15 --output '/results/$track.json'" || run_status=$?
mkdir -p artifacts/evaluation
rsync -a "$remote:$project/artifacts/evaluation/$track.json" "artifacts/evaluation/$track.json"
PYTHONPATH=backend .venv/bin/python -m evaluation.report "artifacts/evaluation/$track.json" --output "artifacts/evaluation/$track"

exit "$run_status"
