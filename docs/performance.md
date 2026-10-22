# Local performance measurements — October 22, 2026

Baseline: `57ff14f9ac83e80ff60fc7930e15a6e5fb43183c`. Optimization: cache immutable weekly league scores for standings, with a 128-entry LRU keyed by season, week, and run seed. Full box scores are not retained in this cache.

Profiling one sequential 17-week season found 2,703 calls to `simulate_game`. Rebuilding standings repeatedly simulated prior weeks. With the score cache, the same workload makes 663 calls. The remaining work includes generating current box scores and selected-team history.

## Method

Install Python requirements and run `npm ci`. Run:

```bash
python scripts/benchmark_performance.py
```

To benchmark another checkout with the same harness:

```bash
python scripts/benchmark_performance.py /absolute/path/to/baseline-checkout
```

Each run launches a new local Uvicorn process on unused port 8768, measures startup-to-health separately, and measures the first schedule request separately (including schedule generation). It then requests all 17 regular-season weeks and five postseason snapshots for three fresh seeds (1234, 5678, 9012), plus seven profile requests and seven Week 17 retries. HTTP timings include response reading and JSON decoding. Regular-season totals sum the 17 request times, excluding startup and initial schedule generation. Each seed starts with no score/standings entries for that run; later weeks reuse only already completed weeks.

The same fixture runs through the UI in jsdom: three warmup updates followed by 20 measured updates per mode. These measure JavaScript/DOM construction, **not browser layout, paint, focus behavior, or network delay**. No rendered-browser timing was available.

Baseline and optimized measurements below ran sequentially on the same development host, with no test run executing alongside them. Values are milliseconds; small samples and host load introduce variation. These are local measurements, not deployed-service promises.

## Results

| Measurement | Baseline median | Optimized median |
| --- | ---: | ---: |
| Fresh-run weekly HTTP request (51 requests) | 32.72 | 10.22 |
| Weekly request p95 | 53.85 | 17.93 |
| Full regular-season request total (3 runs) | 572.09 | 210.41 |
| Postseason snapshot (15 requests) | 4.57 | 5.30 |
| Week 17 retry (7 requests) | 6.98 | 7.59 |
| Warm team profile (7 requests) | 2.56 | 1.61 |
| UI DOM update, Schedule view | 19.34 | 19.69 |
| UI DOM update, roster Season Stats mode | 15.95 | 20.08 |
| Scouting roster DOM construction | 5.59 | 5.70 |

The targeted weekly HTTP median fell 69% (3.2× faster); regular-season request totals fell 63%. UI code is unchanged, and no UI, retry, profile, or postseason speedup is claimed from their varying timings.

## Startup and hosting delays

| One-process observation | Baseline | Optimized |
| --- | ---: | ---: |
| Local process start to health-ready | 364.18 | 387.55 |
| First schedule request | 185.67 | 144.90 |
| First team-profile request | 3.60 | 3.47 |

Startup and schedule-generation code are unchanged. Their timing differences are not attributed to this optimization.

Three read-only requests to the deployed `/api/teams` endpoint took 3,347, 3,750, and 3,304 ms from this environment. The service was not deliberately idled or restarted, and hosting logs were unavailable. These network-inclusive observations cannot isolate Render wake-up, routing, or transport costs. Hosting cold-start delay has **not** been measured or fixed; caching reduces application CPU work after the process is running.

## Correctness and limits

- All 87 Python tests and the full UI interaction suite pass locally.
- All 162 complete payload comparisons match the baseline: 30 team profiles, plus weekly and postseason snapshots for Seattle and Las Vegas across seeds 0, 1234, and 5678. Combined SHA-256: `83f536aadcf9da96c136e45080207d86ad7e3ae834e84599cca68fb1c638f83f`.
- Cache tests verify seed/season/week isolation, immutable results, reuse of earlier weeks, and identical standings after clearing caches.
- Cache entries contain only immutable team-ID/score tuples. The 128-entry bound limits retained weeks; eviction or process restart causes recomputation with identical results. Separate server workers have separate caches. Simultaneous cache misses may duplicate pure computation.
