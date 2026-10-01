# Explorer verification

This report covers the consumer, fixture regression tests, and live MexicoDev integration. Consumer checks do not independently establish employer legitimacy or producer classification accuracy.

## Automated coverage

`test.sh` runs backend pytest, frontend Vitest/type checks, and Playwright. Coverage includes snapshot restarts, incomplete refreshes, stale fallback, expiry/withdrawal, source URL validation, concurrent cost reservations, monthly caps, uncertain bills, session isolation, and global concurrency. Frontend coverage includes hard eligibility conflicts, unknown evidence, preference indicators, related-role limits, local search, stale refinement responses, and safe links.

Browser checks exercise search, evidence details, device persistence, requirements, clarification, graph/list switching, dragging/hover, keyboard focus and Escape, reduced motion, touch selection, timeline records, skill intersections, public HTML pages, withdrawal refresh behavior, and a 100-bubble drag measurement. Platform-specific checks are skipped on the other device rather than reported as covered twice.

Latest checks: 22 backend tests, 12 frontend tests plus strict TypeScript checking, and 29 browser checks passed. Three device-specific browser checks were intentionally skipped on the other device. Coverage also verifies that semantic refinement can broaden keyword results and changing preference weights does not trigger inference. Production builds also completed with Node 24 in the test-host Docker build.

Measured on an AMD Ryzen AI 7 350 workstation (16 logical CPUs), without deliberate CPU/network throttling:

| Measurement | Result | Conditions |
| --- | --- | --- |
| Local search p95 | 21.36 ms | 10,000 synthetic records, 30 samples, Node 25.1.0; excludes rendering/network |
| Graph frame rate | 60.00 FPS | 100 bubbles, active pointer drag, Chromium headless, 1280 x 1100 viewport |
| Graph frame interval p95 | 16.8 ms | Same 120-frame sample; first five frames excluded |

These are lab measurements on fixture data. They do not establish end-to-end browser search p95, mobile frame rate, real-user Web Vitals, or live upstream performance. Reproduce the ranking benchmark with `node scripts/benchmark-search.mjs` and the graph measurement with Playwright.

## Deployment and provider checks

The MexicoDev key is a backend-only Docker secret. Authenticated catalog, search, market, and status requests succeeded on 2026-10-01 UTC. The populated feed exposed transport differences now handled by the consumer adapter: nullable titles, 0–3 rubric scores, dimension names, evidence quotes, market comparison parameters, and advertisement-wrapped drilldowns. A live catalog of 391 jobs loaded successfully. Forty distributed sample records passed evidence-reference and source-offset checks. Completed, elapsed-window, and all-retained chart counts matched their drilldown totals. These checks inspect contract consistency, not independent screening accuracy.

The two project-prefixed services run on the test host with read-only filesystems, dropped capabilities, non-root users, memory/PID/CPU limits, private backend networking, and Docker secrets. PostgreSQL 18.4 hosts an isolated `jev` database/schema with operational tables only.

HTTPS routing at the proposed hostname succeeds with an explicit host override to `10.0.2.36`. Ordinary hostname DNS is not configured. The HTTP/2 response includes per-request nonce CSP, HSTS, frame denial, content-type protection, a restrictive permissions policy, and preview noindex. Container health checks passed. The final deployed browser smoke passed with zero browser errors after correcting deterministic UTC rendering. Search, graph loading, and evidence details were exercised through HTTPS.

After switching to live mode, the deployed browser smoke passed with 391 catalog jobs, 100 visible bubbles/list rows, a successful budgeted Jev refinement, source evidence, market drilldowns, and a second-skill intersection. No browser errors occurred. Live mode removes the fixture banner and fixture-only noindex policy. The browser regression suite passed 19 checks with three intentional device-specific skips after isolating simulated client identities; the first run had exhausted the shared test IP rate bucket. Production rate limits were unchanged.

A single internal live TypeSafe call used the same transactional reservation path as public refinement. Pinned `jev-1.13.0` returned two relevance judgments for the retrieved synthetic candidates; reported cost was $0.00002205. Budgeted public refinement is enabled with the live feed. This verifies model access and usage reconciliation, not real-job classification accuracy or relevance calibration.

## Full audit scope

The requested full-audit workflow reviewed security, SEO, GEO, performance, and dependencies. Findings about initial HTML job discovery, preview indexing/provenance, public-detail metadata, transient job-page failures, SSR rate-limit identity, and blocking catalog refreshes were corrected. Source and browser tests are separate from deployed observations.

The dependency review found no reported npm or pip advisories at audit time. Production builds use Node 24 and Python 3.13; the workstation's Node 25 is outside support, so production-container builds provide the relevant Node 24 build check. Runtime Python requirements exclude pytest and unused parser packages. Base-image tags remain mutable; OS-image vulnerability scanning and artifact digest pinning are not claimed.

Remaining verification: ordinary DNS access, real-data ranking quality, upstream outage/withdrawal behavior in production, long-running PostgreSQL concurrency under traffic, and real-user Web Vitals. No production rollout is included.

## Jobmap hostname deployment

The test hostname is now `jobmap.home.iktdts.com`. Deployment configuration, backend origin validation, canonical metadata, sitemap/robots fallbacks, and the smoke script use the new name. The existing internal DNS CNAME points to `projects.home.iktdts.com` (`10.0.2.36`). Ordinary DNS resolution and HTTPS 200 with certificate validation passed; a host override is no longer required. Earlier DNS-pending notes above describe the previous hostname.

## Natural-language filtering and expenses

Corrected a search bug where common words matched almost the entire catalog and Jev merely reordered the results. Successful refinement now selects the result set at relevance >= 0.65. Retrieval ignores conversational filler and prioritizes domain terms before bounded inference. A one-second debounce restarts on each edit, defers during composition, and cancels on clearing. Regression checks cover the exact robotics query, exclusion of low-scored and unevaluated jobs, typed input across the debounce interval, composition, stale responses, and no inference from preference weights. Expense tests assert reported-token reconciliation, no additional ledger entries for cached results, conservative reservations after uncertain failures, and daily/monthly concurrency limits.

The deployed HTTPS smoke for “I want to build robots” returned 5 Jev-approved matches from the 391-job catalog. The smoke verifies every displayed result ID is in the above-threshold model response, then exercises evidence details and market intersection. No browser errors occurred.

## Visible costs

A public aggregate `/api/usage` powers the always-visible Jev costs panel below the header. UTC daily/monthly charges, reservations, remaining budgets, charged-call counts, and availability refresh every 30 seconds and after refinement. Costs exclude the separate MexicoDev ingestion allocation, which is labeled. Tests verify separate reserved/charged amounts, reset dates, omission of private call identifiers, desktop/mobile visibility, and manual refresh without inference.

## Short keyword relevance

Reproduced `agent` returning no jobs because the earlier relevance question scored the explicit Agent Builder title at 0.38. The revised question treats short keywords as broad job searches and clear title/skill/domain matches as sufficient evidence. A budgeted live evaluation scored Agent Builder at 0.90. Retrieval and local matching also include agentic roles. The rubric cache version was incremented so prior judgments are not reused.

Deployed browser checks now show six results for `agent`, including Agent Builder, with the costs panel visible. The requested recording of `I want to build robot` returned eight matches with zero browser errors. Saved `artifacts/jobmap-robot-search.webm` and an H.264 MP4 copy (15.4 seconds); visually checked the results frame.

## Filters, color guide, and cost navigation

Moved costs into a dedicated Usage & costs view to preserve discovery space. Added an always-visible graph color guide on desktop and mobile, generated from the same palette as the nodes. Category names also appear on focus/hover and in accessible bubble labels. Added local location/country, work arrangement, salary disclosure, and minimum-pay filters; the latter keeps currency and period separate and compares the lower bound. Location is now preserved from the upstream compact record. Filter changes make no inference calls.

## Search comparison and one-time animation (2026-10-01)

- Backend: 27 tests passed across the existing feed/refinement suite and new vector/comparison tests. New coverage checks invalid vectors, description fingerprint changes, independent method failure, cache bypass, low cosine scores, stale catalog rejection, and shared eligibility rules.
- Frontend: 12 unit tests passed. Full Playwright run: 37 passed, 3 device-specific skips; targeted follow-ups passed for comparison, reduced motion and one-time animation. Type checking and the deployed production build passed.
- Test deployment: pgvector 0.8.3 enabled in the existing `jev` database. All 397 current jobs have a stored description and a 384-dimensional vector from each of three models (1,191 vectors). SQL confirmed stored dimensions and self-cosine distance of zero. All three services healthy. The encoder used approximately 557 MiB during indexing within its 1.5 GiB cap.
- Real comparison smoke queries: `I want to build robots`, `Python backend engineer`, `Frontend React developer`; all four methods succeeded on the same 237-posting corpus for the default 45-day window. Jev elapsed server times were 211, 208 and 214 ms; the three vector pipelines ranged from 25 to 53 ms. These are individual concurrent warm-model observations, not aggregate latency guarantees. Initial indexing is excluded.
- The robots query returned eight Jev results above 0.65. Each embedding column showed its top ten without a cosine cutoff. These are returned counts, **not relevance or accuracy measurements**. No human labels were supplied, and no accuracy winner is claimed. The UI lets a reviewer judge the full postings and export ratings with each run.
- Reproduce the live observations with `node scripts/benchmark-comparison.mjs 'I want to build robots'`. It records results and methodology in `artifacts/comparison-benchmark.json` and exits unsuccessfully if any method is unavailable. The comparison uses the existing Jev candidate pipeline versus full-corpus embedding retrieval; the UI discloses the different candidate and text coverage.
