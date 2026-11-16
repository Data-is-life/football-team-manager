# Development

[Project overview](../README.md) · [Player quick start](../QUICKSTART.md)

## Local setup

Use Python 3.12, matching `.python-version` and CI. From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

On Windows, activate the environment with `.venv\Scripts\Activate.ps1` in
PowerShell. Open <http://127.0.0.1:8000>. FastAPI serves the UI and API together;
no frontend build step or database is required.

## Checks

Run the Python checks from the repository root:

```bash
python -m unittest discover -s tests -v
```

For UI checks, also install Node.js 24+ and the Python dependencies above:

```bash
npm ci
node --check app/static/app.js
npm run test:runner
npm run test:ui
```

UI interaction suites use jsdom and local FastAPI servers. They cover navigation,
game and offseason flows, retries, saves, and replay; they do not verify visual
layout. Node dependencies are for development checks only.

The UI runner defaults to two workers. Use `npm run test:ui -- --workers=1` for
sequential debugging, or set 1–4 workers. Run one full UI command at a time
because the suites use fixed ports. For timing output:

```bash
npm run test:ui -- --report=ui-timings.json
```

CI runs the Python, JavaScript syntax, runner, and UI checks on pull requests and
pushes to `main`. See [test timings](test-performance.md),
[API/UI performance](performance.md), and [career benchmarks](../benchmarks/README.md)
for measurement methods and limitations.

## Deploy with Render

The root `render.yaml` defines one free Python web service on `main`.

1. In [Render](https://dashboard.render.com/), choose **New → Blueprint**.
2. Connect `Data-is-life/football-team-manager` and select `main` with the root
   `render.yaml`. Confirm the **Free** instance plan.
3. Wait until the deploy is live, then open the service URL.

The Blueprint installs `requirements.txt` and starts
`python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
Its health check is `/api/teams`, and `autoDeployTrigger: checksPass` waits for
checks before deploying changes on `main`. Opening a PR does not update the live
game or create a preview service. After a merged deploy goes live, refresh the game.

The free service may sleep when idle, so the first request can take longer.
Progress lives in browser local storage, independently of the server process.

## Where things live

| Path | Purpose |
| --- | --- |
| `app/` | Python league rules, simulation, career state, and API |
| `app/static/` | Browser UI, styles, and JavaScript |
| `app/data/` | Bundled player names; [sources and editing](../app/data/README.md) |
| `tests/` | Python and UI interaction checks |
| `scripts/` · `benchmarks/` | Test runner and performance tools |
| `render.yaml` · `.github/workflows/tests.yml` | Hosting and CI configuration |

Game rules and save replay are versioned. Consult the
[rules reference](rules-reference.md) before changing mechanics that could affect
existing careers or deterministic results.
