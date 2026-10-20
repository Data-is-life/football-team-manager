from dataclasses import asdict
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .league import GROUPS, TEAM_BY_ID, generate_schedule, rotating_group, schedule_payload, teams_payload
from .playoffs import playoffs_through_round
from .player_stats import aggregate_player_stats
from .simulation import ROSTER_RULES, roster_for, simulate_through_week, team_ratings
from .attributes import ATTRIBUTE_INFO, attribute_keys


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Arcade League", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/teams")
def list_teams() -> dict[str, object]:
    return {"groups": list(GROUPS), "teams": teams_payload()}


@app.get("/api/team/{team_id}")
def team_profile(team_id: str) -> dict[str, object]:
    if team_id not in TEAM_BY_ID:
        raise HTTPException(status_code=404, detail="Team not found")
    players = list(roster_for(team_id).values())
    return {
        "team": asdict(TEAM_BY_ID[team_id]),
        "ratings": asdict(team_ratings(team_id)),
        "roster": [{**asdict(player), "attributes": {
            key: getattr(player.attributes, key) for key in attribute_keys(player.position)
        }} for player in players],
        "roster_stats": aggregate_player_stats(players, []),
        "roster_rules": [
            {"position": position, "initial": initial, "minimum": minimum,
             "count": sum(player.position == position for player in players),
             "attributes": [
                 {"key": key, "label": ATTRIBUTE_INFO[key][0], "description": ATTRIBUTE_INFO[key][1]}
                 for key in attribute_keys(position)
             ]}
            for position, (initial, minimum) in ROSTER_RULES.items()
        ],
    }


@app.get("/api/schedule/{team_id}")
def team_schedule(
    team_id: str,
    season: int = Query(default=1, ge=1, le=999),
) -> dict[str, object]:
    if team_id not in TEAM_BY_ID:
        raise HTTPException(status_code=404, detail="Team not found")
    team = TEAM_BY_ID[team_id]
    games = generate_schedule(team_id=team_id, season=season)
    return {
        "team": {"id": team.id, "city": team.city, "group": team.group},
        "season": season,
        "rotating_group": rotating_group(team.group, season),
        "games": schedule_payload(games),
    }


@app.get("/api/season/{team_id}/week/{week}")
def simulate_week(
    team_id: str,
    week: int,
    season: int = Query(default=1, ge=1, le=999),
    run_seed: Annotated[int, Query(ge=0, le=4294967295)] = 0,
) -> dict[str, object]:
    if team_id not in TEAM_BY_ID:
        raise HTTPException(status_code=404, detail="Team not found")
    if week < 1 or week > 17:
        raise HTTPException(status_code=400, detail="Week must be between 1 and 17")
    return simulate_through_week(team_id=team_id, season=season, week=week, run_seed=run_seed)


@app.get("/api/playoffs/{team_id}/round/{round_number}")
def playoff_round(
    team_id: str,
    round_number: int,
    season: int = Query(default=1, ge=1, le=999),
    run_seed: Annotated[int, Query(ge=0, le=4294967295)] = 0,
) -> dict[str, object]:
    if team_id not in TEAM_BY_ID:
        raise HTTPException(status_code=404, detail="Team not found")
    if round_number < 0 or round_number > 4:
        raise HTTPException(status_code=400, detail="Playoff round must be between 0 and 4")
    return playoffs_through_round(team_id, season, round_number, run_seed)
