# Job search evaluation

This suite separates deterministic controlled quality measurements from real-job relevance judgments. Real-job labels can come from blinded humans or an independent LLM judge; LLM labels are explicitly provisional, never presented as human ground truth. Jev and embedding scores never become relevance labels.

## Run it

From the repository root, using the existing test deployment:

```sh
./scripts/run-search-evaluation.sh controlled 2
./scripts/run-search-evaluation.sh live 2
```

Each command starts a one-off backend container with the evaluation code mounted read-only. The running website is not rebuilt or restarted. The controlled corpus lives in session-local PostgreSQL tables, never in the production job index. All Jev calls use the application’s existing daily/monthly spending reservations, plus a $0.15 cap per run. Only one benchmark can run at a time. Public endpoint rate limits are unchanged; the administrator-run benchmark calls the same implementation directly, one query at a time.

Outputs are saved under `artifacts/evaluation/`:

- `controlled.json` / `live.json`: corpus snapshot, query definitions, model/version metadata, all rankings, timings, failures and protocol. These are the raw evidence, not just aggregate scores.
- `controlled/report.html` / `live/report.html`: readable report, with metrics JSON and CSV alongside it.
- `controlled/blind-grade.html` / `live/blind-grade.html`: standalone, offline grading pages. Model names, scores, rankings and expected labels are omitted from the grading data.

The latest run replaces the corresponding output. Copy a run and its reports before starting another run if you want to preserve it. Snapshot exports contain posting text; handle and retain them according to your source-data policy.

For direct execution inside a backend environment with database and encoder access:

```sh
python -m evaluation.runner --track controlled --repeats 2 --max-usd 0.15 --output /tmp/controlled.json
```

## Controlled track

The frozen `job-search-controlled-v1` set contains 72 fictional English postings and 48 queries. Every posting explicitly declares role, duties, work location, seniority, employment type, degree requirement and pay. Expected matches are deterministic consequences of those facts and were defined before inference. All model-visible posting text is at most 1,000 characters, so Jev and embeddings receive the same text.

Sixteen development queries and 32 test queries have disjoint job topics. Query categories include keywords, paraphrased intent, combined requirements, exclusions and no-match cases. The corpus, queries and labels have a SHA-256 fingerprint. Keep the set fixed when comparing changes; create a new version if you revise it.

Seven methods run:

1. The deployed Jev pipeline, including its lexical/alias candidate selection of up to 30 jobs.
2. MiniLM cosine retrieval over the entire corpus.
3. BGE cosine retrieval over the entire corpus.
4. Arctic cosine retrieval over the entire corpus.
5. BM25 keyword retrieval (`k1=1.2`, `b=0.75`).
6. Jev scoring every posting, in batches of 24, with the same relevance question as the deployed app.
7. MiniLM retrieval of 20 candidates followed by Jev scoring those candidates.

Document embeddings are produced by the real deployed models. Retrieval uses exact pgvector cosine search in temporary tables. Controlled methods run sequentially in seeded randomized order, so simultaneous methods do not compete for CPU. Posting indexing is timed separately and excluded from query latency. Application result caches are bypassed; upstream provider caching is opaque.

This is a diagnostic synthetic set, not an estimate of production accuracy. Short, regular postings and explicit requirements are easier to label than real job advertisements. There are only five held-out no-match queries, so their percentages are coarse. Broader conclusions need the live track and more independent queries.

## Metrics and calibration

Quality uses repeat zero only. Additional repeats measure latency and top-10 stability, never select the best-quality run after the fact.

Raw ranking metrics are Precision@5, nDCG@10, Recall@10 and reciprocal rank at 10. Queries without any relevant document are excluded from ranking averages and evaluated separately for false positives. Precision divides by `k`, including unfilled positions. Complete controlled labels make corpus recall calculable. Missing judgments are never treated as negative labels.

Each method’s cutoff maximizes macro F1 on development queries only, then is applied unchanged to held-out test queries. For calibration, a no-match query with no returned jobs receives F1=1; any false positive gives F1=0. This abstention convention is reported explicitly. BM25 cutoffs can exceed 1; cosine scores and Jev probabilities are not treated as the same scale.

The best embedding reference is selected on development nDCG, not test results. Paired nDCG differences use 2,000 seeded bootstrap resamples of matched test queries. These intervals describe variation within this small query set, not reviewer disagreement or generalization to every job-search workload.

Median and p95 latency pool successful queries/repeats; failure counts appear separately. API costs use recorded tokens and the app’s configured accounting rate. Local encoding has no API charge, but CPU, hosting, storage and indexing are not free and are not assigned a dollar cost here.

The metric definitions follow standard IR practice; useful references are [BEIR](https://github.com/beir-cellar/beir) and [pooled relevance judgments](https://www.microsoft.com/en-us/research/publication/pooled-evaluation-over-query-variations-users-are-as-diverse-as-systems/).

## Real-job blind grading

The live track freezes the current eligible 45-day corpus and uses the same 48 predefined searches. It runs the four deployed methods as the comparison UI does. Candidate coverage and posting-text coverage differ between the existing Jev pipeline and embeddings; this remains a pipeline comparison. A changed catalog invalidates the run’s fixed-corpus claim.

The grading pool contains the union of each method’s top ten results from the first repeat, plus two randomly selected postings per query where available. Each query/posting pair appears once, in shuffled order. The page hides which method returned the posting and its score.

Open `artifacts/evaluation/live/blind-grade.html`, rate postings, and export the judgments JSON. Use 0 for irrelevant, 1 for partial relevance or missing information, and 2 for a strong match. An explicit conflicting requirement is irrelevant. Skip uncertain cases. Use the Search selector to finish one query’s pool at a time. Each reviewer identifier has separate browser storage so a second reviewer does not inherit the first reviewer’s ratings. Ratings save in browser storage when available; the exported JSON is the portable record.

Recompute the report:

```sh
PYTHONPATH=backend .venv/bin/python -m evaluation.report \
  artifacts/evaluation/live.json \
  --labels /path/to/judgments.json \
  --output artifacts/evaluation/live-reviewed
```

A second reviewer can independently grade a subset. Pass multiple `--labels` files to merge agreements; conflicting pairs remain unjudged until adjudicated. After resolving a disagreement, use a resolved judgment file instead of the conflicting originals. Files from another run/corpus and invalid grades are rejected.

For fair averages, a live query enters quality metrics only after the whole grading pool for that query is judged and every method succeeded. The report then shows Precision@5 and **pooled** nDCG@10 on a common set of queries. It does not claim corpus-wide recall or prove that an empty judged pool means no relevant job exists elsewhere. Partial grading is still useful, but it cannot silently become a complete ground truth.

## Test the evaluation code

```sh
.venv/bin/pytest backend/tests/test_evaluation.py -q
```

Tests cover hand-computed ranking metrics, missing and duplicate results, no-match handling, calibration with scores above 1, paired intervals, corpus/split invariants, invalid label imports, and the explicit-candidate Jev hook. Application API schemas do not expose that internal hook.

## Automated LLM judging

`evaluation.judge` compares each request with the full posting and explicit job metadata using an independent LLM. It sends no method names, rankings, retrieval scores or expected answers. A shared query/job pair is judged once for every search method. The existing live snapshot has 1,399 unique pairs across 48 queries. No search rerun or re-embedding is needed.

Set `EVAL_JUDGE_MODEL`, `EVAL_JUDGE_BASE_URL` (default `https://api.openai.com/v1`), and `EVAL_JUDGE_API_KEY` in your execution environment. `OPENAI_API_KEY` is also accepted. A local endpoint can omit credentials. Use a Chat Completions endpoint supporting strict JSON-schema output and `max_completion_tokens`; the base URL includes `/v1`, not `/chat/completions`. Pick a judge independent of Jev, preferably a pinned model version. Never paste credentials into reports or commit them.

```sh
# Check workload without making calls.
PYTHONPATH=backend .venv/bin/python -m evaluation.judge \
  artifacts/evaluation/live.json --output artifacts/evaluation/live-llm --dry-run

# Model and credentials come from the environment. Run all current pairs.
PYTHONPATH=backend .venv/bin/python -m evaluation.judge \
  artifacts/evaluation/live.json --output artifacts/evaluation/live-llm \
  --max-calls 1400 --concurrency 4
```

The default is at most 50 new calls per invocation. This is a call cap, **not a dollar cap**; judge billing is separate from the app's Jev budget. Check your chosen model's prices and account spending limit before a large run. Token usage and elapsed time are saved per attempt. Judge timing is never mixed into search latency. Output is capped at 1,024 tokens per call, configurable with `--max-output-tokens` for models needing more. Full descriptions are retained; oversized requests fail rather than silently truncate text.

Run the same command to resume. Atomic checkpoints save each attempt and valid judgment. Successful calls are reused; failed/interrupted calls remain unjudged and are not automatically retried. `--retry-failed` explicitly allows retrying them, potentially incurring another charge. A filesystem lock prevents simultaneous writers. A different run, dataset, model, endpoint, rubric, or token setting requires a different output directory. Exit status 2 means incomplete; partial reports are still generated, using only queries whose entire shared pool is judged.

Outputs in the chosen directory:

- `report.html`: all four methods scored against the same LLM labels, visibly marked provisional; includes ordinary and strong-match precision.
- `judged-jobs.html`: every request, posting, grade, explanation, evidence, unknowns and unmet requirements.
- `judgments.json`: resumable checkpoint, judge provenance, rubric hash, usage and timings; also works with `evaluation.report --labels`.

Grades are 0 (irrelevant or explicit conflict), 1 (partial match or missing requested information), and 2 (strong supported match). A claimed strong match with unmet/unknown requirements, an invented evidence quote, refusal, malformed output or truncated response is not accepted as a label. Model-reported confidence is diagnostic, not a calibrated probability. Existing Precision@5 counts grades 1 and 2; strong-match Precision@5 counts grade 2 only. Corpus-wide recall stays unavailable with pooled judgments.

Manual grading is optional. For stronger evidence, run a second independent judge into a separate directory and compare conclusions. Supplying both judgment files to `evaluation.report` retains agreements and leaves conflicts unjudged. This measures judge sensitivity without pretending agreement proves correctness. The controlled benchmark keeps its deterministic labels unchanged.

API format reference: [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

### GPT-6.1 Sol with explicit caching

For `--model gpt-6.1-sol`, the runner uses the Responses API with low reasoning effort, `store: false`, and explicit 30-minute cache breakpoints after the stable rubric and after the posting. The changing search request follows those boundaries and is not written to cache. Cases are grouped by posting, with sequential requests per posting and concurrency across postings. Actual cache-read and cache-write token counts are retained from the API. Caching is verified from usage, not assumed from a stable prefix.

The authorized StaffAI secret can be read directly at runtime without copying it into this project:

```sh
EVAL_JUDGE_MODEL=gpt-6.1-sol \
EVAL_JUDGE_API_KEY_FILE=/home/iktdts/apps/bots/staffai-bot/secrets.prod/openai_api_key.txt \
PYTHONPATH=backend .venv/bin/python -m evaluation.judge \
  artifacts/evaluation/live.json --output artifacts/evaluation/live-gpt61-sol \
  --max-calls 1400 --concurrency 16 --max-output-tokens 4096
```

`usage.json` separates input, cache reads, cache writes, output and reasoning tokens. Reasoning tokens are already included in output. Estimated cost uses published standard GPT-6.1 Sol rates: $2/M uncached input, $0.10/M cached input, $2.50/M cache writes, $10/M output. It is not an invoice and excludes account-specific discounts, regional premiums and taxes. The report includes these numbers and a comparison using the same token counts without caching.

The expanded rubric remains fixed for the entire evaluation. All model-visible data is blind to retrieval identity and ranking. No new labels replace the original deterministic controlled-suite labels. Authentication, invalid-request, missing-model and rate-limit errors stop new requests to avoid repeating a systemic failure; completed judgments remain resumable.
