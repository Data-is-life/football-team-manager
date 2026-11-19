# Selecting CI checks

The League checks workflow always starts, keeping the existing required `tests`
check available. Pull requests select test groups from the merge-base-to-head
diff, including deleted files and both paths of a rename.

| Change | Python | UI |
| --- | --- | --- |
| README, QUICKSTART, LICENSE or files under docs/ only | Skip | Skip |
| app/static/, tests/ui_*.cjs or scripts/run-ui-tests.cjs | Skip | Run |
| Backend, Python tests/fixtures, dependencies, CI or any unknown path | Run | Run |
| Mixed frontend and backend | Run | Run |
| Push to main or manual workflow run | Run | Run |

Both groups run in parallel when selected. The UI job still installs Python API
dependencies because browser interaction tests start the real backend. It runs
JavaScript syntax, UI-runner tests and the complete interaction suite. Frontend
changes to the shared app.js run all UI tests, rather than trying to infer which
feature a line affects.

The final `tests` gate always evaluates change detection and selected jobs.
Failures, cancellations, missing outputs and unexpectedly skipped selected jobs
fail the gate. An intentionally unselected group may be skipped. The complete
workflow is never path-filtered, avoiding pending required checks on docs PRs.
New commits cancel superseded runs on the same PR/ref.

To force both groups, use Actions → League checks → Run workflow. All merges to
main also run both, regardless of the PR selection. A workflow/classifier change
itself selects both groups.

Local routing/gate checks:

```sh
python -m unittest discover -s tests -p test_ci_changes.py -v
```
