# Football Team Manager

A browser football GM game: rebuild a fictional franchise, develop players,
manage contracts, and compete for a championship across multiple seasons.
Python/FastAPI runs the simulation; vanilla JavaScript renders the game.

## Play

Choose a city, take over before the final regular-season game, and build from
there. Simulate games week by week, follow the playoffs, then draft, negotiate
contracts, and prepare your roster for the next season.

- **30 teams**, six groups, a 17-game schedule, and 14 playoff places.
- **Roster building** with current/potential ratings, development, retirement,
  a six-round draft, free agency, guaranteed contracts, and payroll limits.
- **Franchise progress** with live standings, scouting, team rankings, player
  stats, GM records, and browser autosaves.

Read the [two-minute player guide](QUICKSTART.md), or open **How to Play** in the game.
Progress is saved in this browser; clearing site data removes it, and a new
career replaces the previous save. There is no account or cross-device sync.

## Run locally

Use Python 3.12:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>.

## Documentation

| Read | For |
| --- | --- |
| [Quick start](QUICKSTART.md) | Playing your first season and offseason |
| [Offseason rules](docs/offseason.md) | Signing, fixed-price free agency and development |
| [Development](docs/development.md) | Setup, tests, deployment, and project layout |
| [Rules and version history](docs/rules-reference.md) | Formulas, detailed mechanics, and older-save compatibility |
| [Performance](docs/performance.md) · [Test timings](docs/test-performance.md) · [Career benchmarks](benchmarks/README.md) | Measurements and reproducible checks |
| [Player name data](app/data/README.md) | Sources and editing the bundled names |

Older careers may follow earlier rules. Detailed historical notes live in the
reference file so this page stays focused on getting started.
