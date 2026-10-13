# Arcade League starter

Python owns the league rules and schedule generation. The browser layer only renders the interface and sends user choices to the API.

## Included

- 30 city-only teams in six groups
- player team selection that gives way to a team home screen
- team offense/defense ratings and a six-player roster with positions and scouting ratings
- roster show/hide controls and a team-change flow with a keep-current-team option
- 17-game Python schedule generator
- 8 home/away group games
- 5 same-place games based on the prior season
- 4 remaining opponents from a rotating group
- five-season group rotation
- responsive schedule screen
- one-click, week-by-week simulation
- deterministic fictional rosters and team ratings
- final score, team comparison, and player box scores
- season record that updates after every completed game
- a separate compact League Results section with the other 14 weekly scores
- one coherent league schedule: 15 games per week and no duplicate team appearances
- all six group standings recalculated after every simulated week
- a provisional 14-team playoff field: six group winners plus eight wildcards
- first-round byes for seeds 1 and 2
- tiebreakers in order: head-to-head, common-opponent record, point differential, points scored, deterministic random draw

Player scouting ratings are deterministic estimates out of 99. The current simulation uses team offense and defense ratings; individual scouting ratings do not yet affect results.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Play online with Render

The FastAPI app serves both the game interface and API from one web service. The root `render.yaml` configures a free Render service, and `.python-version` selects Python 3.12 for hosting and CI.

After merging the deployment setup:

1. Sign in to [Render](https://dashboard.render.com/).
2. Choose **New → Blueprint**, connect GitHub, and select `Data-is-life/football-team-manager`. If the repository is private, grant Render access to this repository.
3. Use the `main` branch and the root `render.yaml`. Confirm that the web service uses the **Free** instance plan before creating the Blueprint.
4. Wait for the first deploy to become live, then open the service URL shown by Render.

Render builds with `python -m pip install -r requirements.txt` and starts the app with `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT`. The `/api/teams` route is the health check.

### Try each merged PR

GitHub Actions runs the league tests on pull requests and pushes to `main`. Once you merge a PR and the checks on `main` pass, Render automatically deploys that commit to the same URL. Wait for Render to show the new deploy as live, then refresh the game.

Opening a PR alone does not update the main game URL. This setup does not create separate PR preview services.

### Demo behavior

- The free service sleeps after 15 minutes without traffic; the next visit can take about a minute to wake it.
- No database or account is required. The current team and week live in browser memory, so refreshing the page resets your progress.
- Weekly scores are deterministic for the team and season. Replaying the same season produces the same results.
- This starter includes the regular season and playoff race; postseason games are the next build slice.

See Render's [FastAPI guide](https://render.com/docs/deploy-fastapi), [free-tier limits](https://render.com/docs/free), and [automatic deploy settings](https://render.com/docs/deploys).

## Verify the schedule rules

```bash
python -m unittest discover -s tests -v
```

## Next build slice

Add the 14-team playoff bracket and postseason simulation. The leaderboard service for the wider arcade can remain separate and be shared by every future game.
