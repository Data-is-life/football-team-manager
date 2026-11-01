# UI test execution timing

Measured 2026-11-01 against `b2683f00c6d49d3a039eb722422665ff28602720`. The same 14 unchanged interaction suites ran first through the original sequential command, then through the two-worker runner. Each invocation started fresh Node/jsdom and uvicorn processes, preserving per-suite isolation, all scenarios and existing timeouts. Dependency installation is excluded. Python 3.12.14, Node 24.22.1, Linux, 8 CPU quota and 8 GiB memory. These are single local samples, not statistical estimates or promises about GitHub-hosted runners.

| Execution | Wall time | Result |
| --- | ---: | --- |
| Original sequential command | 104.943s | 14/14 passed |
| Two-worker runner | 60.514s | 14/14 passed |

Elapsed interaction-test time fell **42.3%** locally. Per-suite time can increase under contention; elapsed wall time improves because independent suites overlap. Start the measured longest suite (`ui_tabs.cjs`) first, then fill worker slots with the other discovered suites. A default of two bounds CPU/memory pressure; no suites or scenarios are removed.

| Suite | Sequential seconds | Concurrent seconds |
| --- | ---: | ---: |
| ui_tabs.cjs | 24.325 | 26.872 |
| ui_save.cjs | 3.505 | 3.370 |
| ui_seasons.cjs | 10.359 | 11.210 |
| ui_draft.cjs | 10.335 | 11.091 |
| ui_cuts.cjs | 6.927 | 7.857 |
| ui_development.cjs | 4.716 | 4.890 |
| ui_gm.cjs | 3.432 | 3.694 |
| ui_contracts.cjs | 5.378 | 6.466 |
| ui_restore.cjs | 3.373 | 3.635 |
| ui_simulate_season.cjs | 9.866 | 10.850 |
| ui_starters.cjs | 7.474 | 7.942 |
| ui_late_start.cjs | 5.272 | 5.734 |
| ui_rookie_reveal.cjs | 5.138 | 5.318 |
| ui_leaders.cjs | 4.843 | 5.091 |

The earlier [GitHub Actions run](https://github.com/Data-is-life/football-team-manager/actions/runs/41344242053) spent 132 seconds in UI interaction checks and 35 seconds in Python checks. That observation identified UI execution as the largest step; it is a different machine and must not be compared directly to the local after time. GitHub runner CPU availability, queueing, dependency setup and load vary. This PR keeps the existing `tests` job and all Python checks; its new CI run is the appropriate place to assess hosted timings. Render cold starts are unrelated: these tests start their own local servers.

## Reproduce

Install the existing Python requirements and run `npm ci`, then:

```bash
npm run test:runner
npm run test:ui -- --workers=1 --report=ui-sequential.json
npm run test:ui -- --workers=2 --report=ui-parallel.json
```

Run these commands sequentially so fixed per-suite ports cannot conflict. Workers accept 1–4, default 2. Reports include per-suite output, results, timeout status and durations. The runner preserves failed output, finishes remaining suites and returns a failing exit status. It handles SIGINT/SIGTERM and kills the whole suite/server process group on Linux/macOS on cancellation or a five-minute suite timeout. Windows uses direct child termination, so descendant cleanup is only verified on POSIX.

Six runner self-checks cover actual overlap and concurrency bounds, exactly-once execution, failure propagation without skipping later checks, timeout failure, discovery excluding helpers/self-tests, and POSIX server-child cleanup. All 14 existing UI suites passed through the new runner. Application source, Python tests, fixtures and UI interaction assertions are unchanged. DOM checks still do not verify browser paint/layout. Raw local timings are in [ui-test-timings.json](../benchmarks/ui-test-timings.json).
