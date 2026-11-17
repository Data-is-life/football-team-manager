# Career transition performance — November 17, 2026

Profiled against `88a5d6ac293331374a902e35e7703a9b3dc77351` (PR #134).
The main repeated work was historical offseason replay, completed draft replay,
and signing/market decisions. Cold career reconstruction also spends significant
CPU time generating historical schedules with the existing NetworkX matcher.
NumPy would not remove those repeated workflows; no dependency was added.

The change caches immutable completed offseason checkpoints (32 entries), draft
results (8), own-player signing phases (8), and market phases (8). Cache keys
include the full incoming context and decisions, including version, seed, rosters,
contracts, development and schedule inputs. Mutable response dictionaries and
roster lists are recreated for callers. Failed phases are not cached.
Eviction or process restart recomputes the same results. Caches are local to each
server worker and do not coalesce simultaneous identical misses.

Reload still warms the shared career reconstruction first, then loads independent
week/playoff and saved-offseason views concurrently. All views must succeed before
restored gameplay is committed. Season-start schedule/profile requests also run
concurrently; saves and gameplay rules are unchanged.

## Reproduce

From a checkout with dependencies installed:

```bash
python scripts/benchmark_transitions.py --save-requests /tmp/transition-requests.json
python scripts/benchmark_transitions.py --root /absolute/baseline-checkout --requests /tmp/transition-requests.json
python scripts/benchmark_transitions.py --requests /tmp/transition-requests.json
```

Run comparisons sequentially without tests competing for CPU. Three trials use
a three-year Seattle career, seed 1234, rules 44, six-round drafts, default
schedule standings, rookie signings, expired-player releases, no user free-agent
signings, and payroll-floor adjustments as required. These are deterministic
endpoint calls, not measurements of a deployed browser session. All 18 complete
payload hashes match between revisions. Raw medians/hashes are in
[transition-results.json](../benchmarks/transition-results.json).

| Python endpoint work | Before | After |
| --- | ---: | ---: |
| Year 1: completed draft to own-player signing | 87 ms | 47 ms |
| Year 2: completed draft to own-player signing | 81 ms | 50 ms |
| Year 3: completed draft to own-player signing | 176 ms | 188 ms |
| Year 3: own-player signing to market | 53 ms | 59 ms |
| Year 3: market finish and season-start development | 278 ms | 261 ms |
| Year 1: next-season profile | 249 ms | 122 ms |
| Year 2: next-season profile | 545 ms | 69 ms |
| Year 3: next-season profile | 836 ms | 77 ms |
| Year 3: empty-cache profile reload | 1,102 ms | 1,136 ms |
| Year 3: repeated profile reload | 1.9 ms | 2.0 ms |

The clear gain is avoiding repeated historical work when a career grows. Draft
reuse helps where its context remains identical; expiring free agents can change
that context. No general speedup is claimed for market completion or empty-cache
reconstruction. Small differences also reflect host noise and cache overhead.
HTTP, network round trips, DOM rendering and hosting wake-up are excluded. The
request-overlap changes are checked for concurrency, atomic failure and retry;
these timings do not quantify their browser latency benefit.

A separate fresh-process run of the same three-year sequence measured peak
resident memory at 56.3 MiB before and 58.5 MiB after. This is one observation,
not a worst-case bound for every cache at capacity.

For further work, profile a deployed request trace to separate hosting wake-up,
network latency and application time. Faster cold reconstruction would require
work on historical schedule generation or a separate persisted-checkpoint design.
NumPy is more plausible for batch simulation/analysis than for these small,
sequential roster transactions; changing numerical or random-generation policies
would require separate replay-compatibility validation.
