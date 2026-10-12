from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .league import GROUPS, TEAM_BY_ID, generate_schedule, rotating_group, schedule_payload, teams_payload
from .simulation import simulate_through_week


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
) -> dict[str, object]:
    if team_id not in TEAM_BY_ID:
        raise HTTPException(status_code=404, detail="Team not found")
    if week < 1 or week > 17:
        raise HTTPException(status_code=400, detail="Week must be between 1 and 17")
    return simulate_through_week(team_id=team_id, season=season, week=week)
