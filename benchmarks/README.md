# Saved-career restoration measurements

Measured 2026-10-30 against baseline commit `1128ebf5a58d66035135e1dee80c49e993344756` (PR #48) and this change. Local Linux, Python 3.12.14, Node 24, uvicorn/FastAPI and jsdom. These are reproducible local measurements, not Render production latency or real-browser paint timings.

## Method

- Three fresh server processes per workload per revision; each gets one empty-cache restore, followed by three warm restores. Tables show medians: 3 empty-cache samples and 9 warm samples per workload. Raw samples include all request/body-read timings and UI render-function time.
- Server startup is measured separately from spawning uvicorn to the first successful `/api/teams` response. Restore timing starts after readiness and includes subsequent team-list loading, loopback HTTP/body parsing, dependent requests, and DOM rendering until the saved-progress-restored status.
- Each benchmark launches and closes its own jsdom page; server caches are retained only between the warm samples of that trial. Baseline and changed runs execute sequentially, without profiling or tests competing for CPU. Shared-host/JIT noise still applies.
- Deterministic checkpoints: first-season Week 0; Season 4 Week 17 after playoffs, four draft picks and legal cuts (three prior completed offseasons); Season 8 Week 8 (seven prior offseasons). Contracts are explicitly disabled in these fixtures so job-security rules do not truncate long-career measurements.
- A request to the deployed Render `/api/teams` endpoint timed out after 20 seconds from this environment. This does not identify cold-start versus network delay, and no Render wake-up improvement is claimed. Local process startup does not reproduce hosting-platform sleep/provisioning.

## End-to-end restore

| Checkpoint | Empty caches before | Empty caches after | Reduction | Warm before | Warm after |
| --- | ---: | ---: | ---: | ---: | ---: |
| Season 1, Week 0 | 0.499s | 0.341s | 31.7% | 0.062s | 0.071s |
| Season 4, completed draft/cuts | 6.983s | 2.225s | 68.1% | 0.263s | 0.236s |
| Season 8, Week 8 | 11.557s | 3.911s | 66.2% | 0.119s | 0.118s |

The focused benefit is restoring multi-season careers with empty caches. Warm restoration is broadly similar, and first-season restore variation is not evidence of a targeted improvement in new-career loading.

## API, rendering, and process startup

API time below is the slowest response/body-read in each empty-cache restore, then the median of the three trials. It includes loopback transport, serialization, queuing and application work; it is not a pure route CPU measurement. Render time sums non-overlapping synchronous profile/schedule/result/postseason/draft render functions and excludes network waiting.

| Checkpoint | Slowest API before → after | Render before → after | Server startup before → after |
| --- | ---: | ---: | ---: |
| fresh | 0.317s → 0.292s | 76ms → 38ms | 640ms → 582ms |
| year4 | 6.698s → 1.872s | 112ms → 115ms | 562ms → 609ms |
| year8 | 11.461s → 3.723s | 90ms → 61ms | 590ms → 627ms |

## Bottleneck and change

The application profile identified historical offseason replay → draft order → standings → league score simulation as the dominant reconstruction path. Standings previously generated independent usage, possession, efficiency, kicking and rotation statistics for all historical league games, even though it only consumes final scores. Concurrent profile/week/playoff restore requests also repeated the same uncached career replay because `lru_cache` does not coalesce simultaneous cache misses.

The score cache now uses the shared scoring/overtime RNG path directly and skips the later independent statistical streams. Full game box scores still execute every existing stream. Restoration requests the career profile once before starting dependent week/playoff requests, while the schedule fetch remains concurrent. Existing complete immutable roster-context cache keys and bounded cache sizes remain intact. No save format, player ability, random draws, schedule, draft policy, standings tiebreaker, contract or season progression rules change.

## Correctness

- All 72 measured page snapshots (36 per revision) are identical for their checkpoint.
- Seven complete API payloads have identical canonical JSON SHA-256 hashes across revisions: fresh profile; Season 4 profile/week/playoffs/cuts; Season 8 profile/week. The payloads cover ratings, potential, rosters, current results, standings, all player stats, postseason, rookies, draft picks, and cuts. See `parity-before.json` and `parity-after.json`.
- Regression checks compare score-only and full games across all six lineup rules, two run seeds, and Weeks 1/9/17 (540 games); prove independent statistical functions are not invoked for standings; and retain cache immutability/separation checks.
- New DOM checks delay the initial profile, assert dependent requests wait, and verify profile/week failures preserve the exact checkpoint and recover through Retry with identical restored content. Existing UI suites cover legacy saves, entire seasons, drafts/cuts, contract rules and GM records.

Validation completed: **151 Python tests, all nine UI suites, and JavaScript syntax checks passed.**

## Reproduce

Install the normal Python requirements and npm dependencies first. From the changed source directory:

```bash
python -m benchmarks.restore_fixture
RESTORE_TRIALS=3 node benchmarks/restore.cjs /path/to/baseline > benchmarks/before.json
RESTORE_TRIALS=3 node benchmarks/restore.cjs . > benchmarks/after.json
python benchmarks/parity_restore.py /path/to/baseline > benchmarks/parity-before.json
python benchmarks/parity_restore.py . > benchmarks/parity-after.json
python -m benchmarks.profile_restore benchmarks/year4.json
python -m unittest discover -s tests -q
npm run test:ui
```

Timing and profiling runs should be sequential; cProfile overhead changes timings and its output must not be substituted for the unprofiled HTTP measurements. A browser HAR and backend telemetry after deployment would be needed to attribute remaining real-world Render wake-up/network delays.
