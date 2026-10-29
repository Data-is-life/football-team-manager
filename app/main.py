import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, StrictInt
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .league import GROUPS, TEAM_BY_ID, generate_schedule, rotating_group, schedule_payload, teams_payload, validate_standings
from .playoffs import playoffs_through_round
from .player_stats import aggregate_player_stats
from .simulation import ROSTER_RULES, roster_for, simulate_through_week, team_ratings
from .attributes import ATTRIBUTE_INFO, attribute_keys
from .ratings import rating_payload
from .lineups import lineup_context, replace_lineup_rosters
from .simulation import ranked_players
from .draft import build_draft
from .career import ROSTER_MAX, offseason, replay_career


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


def request_lineups(seed, rules, season, start, rebuild_team=None):
    try:
        return lineup_context((),seed,rules,season,start,rebuild_team)
    except ValueError as error:
        raise HTTPException(status_code=422,detail=str(error)) from error


@app.get("/api/team/{team_id}")
def team_profile(team_id: str, run_seed: Annotated[int, Query(ge=0, le=4294967295)] = 0,
                 lineup_rules: Annotated[int, Query(ge=1, le=5)] = 1,
                 season: Annotated[int, Query(ge=1, le=999)] = 1,
                 development_start: Annotated[int, Query(ge=1, le=999)] = 1,
                 rebuild_team: Annotated[str | None, Query(max_length=40)] = None) -> dict[str, object]:
    if team_id not in TEAM_BY_ID:
        raise HTTPException(status_code=404, detail="Team not found")
    context = request_lineups(run_seed,lineup_rules,season,development_start,rebuild_team)
    players = list(roster_for(team_id, run_seed, context).values())
    return profile_payload(team_id, players, run_seed, context)


def profile_payload(team_id, players, run_seed, roster_context=()):
    if getattr(roster_context, 'lineup_rules', 1) >= 2:
        players = ranked_players(players)
        rosters = dict(roster_context)
        rosters[team_id] = players
        roster_context = replace_lineup_rosters(roster_context,tuple(rosters.items()))
    return {
        "team": asdict(TEAM_BY_ID[team_id]),
        "ratings": asdict(team_ratings(team_id, run_seed, roster_context)),
        "run_seed": run_seed,
        "lineup_rules": getattr(roster_context, "lineup_rules", 1),
        **({"rebuild_team": roster_context.rebuild_team} if getattr(roster_context, "rebuild_team", None) else {}),
        "roster": [{**asdict(player), **rating_payload(player,roster_context), "attributes": {
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


def parse_prior_standings(raw: str | None) -> tuple[tuple[str, int], ...]:
    """Validate and canonicalize the saved previous-season group ranks for cache keys."""
    if raw is None:
        return ()
    try:
        ranks = json.loads(raw)
        if not isinstance(ranks, dict) or any(type(rank) is not int for rank in ranks.values()):
            raise ValueError("Ranks must be integers")
        validate_standings(ranks)
    except (ValueError, TypeError) as error:
        raise HTTPException(status_code=422, detail="Prior standings must rank all 30 teams 1–5 within each group") from error
    return tuple(sorted(ranks.items()))


@app.get("/api/schedule/{team_id}")
def team_schedule(
    team_id: str,
    season: int = Query(default=1, ge=1, le=999),
    prior_standings: Annotated[str | None, Query(max_length=2000)] = None,
    lineup_rules: Annotated[int, Query(ge=1, le=5)] = 1,
    development_start: Annotated[int, Query(ge=1, le=999)] = 1,
    rebuild_team: Annotated[str | None, Query(max_length=40)] = None,
) -> dict[str, object]:
    if team_id not in TEAM_BY_ID:
        raise HTTPException(status_code=404, detail="Team not found")
    team = TEAM_BY_ID[team_id]
    games = generate_schedule(team_id=team_id, season=season,
                              standings=dict(parse_prior_standings(prior_standings)) or None)
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
    prior_standings: Annotated[str | None, Query(max_length=2000)] = None,
    lineup_rules: Annotated[int, Query(ge=1, le=5)] = 1,
    development_start: Annotated[int, Query(ge=1, le=999)] = 1,
    rebuild_team: Annotated[str | None, Query(max_length=40)] = None,
) -> dict[str, object]:
    if team_id not in TEAM_BY_ID:
        raise HTTPException(status_code=404, detail="Team not found")
    if week < 1 or week > 17:
        raise HTTPException(status_code=400, detail="Week must be between 1 and 17")
    return simulate_through_week(team_id=team_id, season=season, week=week, run_seed=run_seed,
                                 prior_standings=parse_prior_standings(prior_standings),
                                 roster_context=request_lineups(run_seed,lineup_rules,season,development_start,rebuild_team))


@app.get("/api/playoffs/{team_id}/round/{round_number}")
def playoff_round(
    team_id: str,
    round_number: int,
    season: int = Query(default=1, ge=1, le=999),
    run_seed: Annotated[int, Query(ge=0, le=4294967295)] = 0,
    prior_standings: Annotated[str | None, Query(max_length=2000)] = None,
    lineup_rules: Annotated[int, Query(ge=1, le=5)] = 1,
    development_start: Annotated[int, Query(ge=1, le=999)] = 1,
    rebuild_team: Annotated[str | None, Query(max_length=40)] = None,
) -> dict[str, object]:
    if team_id not in TEAM_BY_ID:
        raise HTTPException(status_code=404, detail="Team not found")
    if round_number < 0 or round_number > 4:
        raise HTTPException(status_code=400, detail="Playoff round must be between 0 and 4")
    return playoffs_through_round(team_id, season, round_number, run_seed,
                                  parse_prior_standings(prior_standings), request_lineups(run_seed,lineup_rules,season,development_start,rebuild_team))


class DraftRequest(BaseModel):
    season: int = Field(default=1, ge=1, le=998)
    run_seed: int = Field(default=0, ge=0, le=4294967295)
    lineup_rules: Literal[1, 2, 3, 4, 5] = 1
    development_start: int = Field(default=1, ge=1, le=999)
    rebuild_team: str | None = Field(default=None, max_length=40)
    prior_standings: dict[str, StrictInt] | None = None
    manual_picks: list[str] = Field(default_factory=list, max_length=4)


@app.post("/api/draft/{team_id}")
def rookie_draft(team_id: str, request: DraftRequest) -> dict:
    if team_id not in TEAM_BY_ID:
        raise HTTPException(status_code=404, detail="Team not found")
    prior = parse_prior_standings(json.dumps(request.prior_standings) if request.prior_standings is not None else None)
    try:
        if request.rebuild_team is not None and request.rebuild_team != team_id:
            raise ValueError('Rebuild team must match the managed team')
        context = lineup_context((), request.run_seed, request.lineup_rules,request.season,request.development_start,request.rebuild_team)
        draft, players = build_draft(team_id, request.season, request.run_seed,
                                    tuple(request.manual_picks), prior, context)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {**draft, "profile": profile_payload(team_id, players, request.run_seed, context)}


class CareerStep(BaseModel):
    lineup_rules: Literal[1, 2, 3, 4, 5] = 1
    season: int = Field(ge=1, le=998)
    prior_standings: dict[str, StrictInt] | None = None
    manual_picks: list[str] = Field(min_length=4, max_length=4)
    dropped: list[str] = Field(default_factory=list, max_length=42)


class CareerRequest(BaseModel):
    action: Literal['profile', 'week', 'playoffs', 'draft', 'cuts']
    season: int = Field(default=1, ge=1, le=999)
    run_seed: int = Field(default=0, ge=0, le=4294967295)
    lineup_rules: Literal[1, 2, 3, 4, 5] = 1
    development_start: int = Field(default=1, ge=1, le=999)
    rebuild_team: str | None = Field(default=None, max_length=40)
    prior_standings: dict[str, StrictInt] | None = None
    career: list[CareerStep] = Field(default_factory=list, max_length=998)
    manual_picks: list[str] = Field(default_factory=list, max_length=4)
    dropped: list[str] = Field(default_factory=list, max_length=42)
    week: int = Field(default=1, ge=1, le=17)
    round_number: int = Field(default=0, ge=0, le=4)
    view_team: str | None = None


def ranks_context(ranks):
    return parse_prior_standings(json.dumps(ranks) if ranks is not None else None)


@app.post('/api/career/{team_id}')
def career_action(team_id: str, request: CareerRequest) -> dict:
    if team_id not in TEAM_BY_ID or (request.view_team is not None and request.view_team not in TEAM_BY_ID):
        raise HTTPException(status_code=404, detail='Team not found')
    try:
        if request.rebuild_team is not None and request.rebuild_team != team_id:
            raise ValueError('Rebuild team must match the managed team')
        if any(step.season >= request.season for step in request.career):
            raise ValueError('Past offseasons must precede the current season')
        steps = tuple((step.season, ranks_context(step.prior_standings), tuple(step.manual_picks), tuple(step.dropped), step.lineup_rules)
                      for step in request.career)
        context = replay_career(team_id, request.run_seed, steps, request.lineup_rules,request.season,request.development_start,request.rebuild_team)
        prior = ranks_context(request.prior_standings)
        viewed = request.view_team or team_id
        if request.action == 'week':
            return simulate_through_week(team_id, request.season, request.week, request.run_seed, prior, context)
        if request.action == 'playoffs':
            return playoffs_through_round(team_id, request.season, request.round_number, request.run_seed, prior, context)
        if request.action in ('draft', 'cuts'):
            if request.action == 'cuts':
                draft, cut_context = offseason(team_id, request.season, request.run_seed,
                    tuple(request.manual_picks), tuple(request.dropped), prior, context)
                players = list(roster_for(viewed, request.run_seed, cut_context).values())
                return {**draft, 'dropped': request.dropped, 'cuts_applied': True,
                        'can_continue': len(dict(cut_context)[team_id]) <= ROSTER_MAX,
                        'profile': profile_payload(viewed, players, request.run_seed, cut_context)}
            draft, players = build_draft(team_id, request.season, request.run_seed,
                                        tuple(request.manual_picks), prior, context)
            return {**draft, 'profile': profile_payload(team_id, players, request.run_seed, context)}
        return profile_payload(viewed, list(roster_for(viewed, request.run_seed, context).values()), request.run_seed, context)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
