# Arcade League starter

Python owns the league rules and schedule generation. The browser layer only renders the interface and sends user choices to the API.

## Included

- 30 city-only teams in six groups
- player team selection
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

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Verify the schedule rules

```bash
python -m unittest discover -s tests -v
```

## Next build slice

Add the 14-team playoff bracket and postseason simulation. The leaderboard service for the wider arcade can remain separate and be shared by every future game.
