import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, StrictInt, StrictBool, model_validator
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .league import GROUPS, TEAM_BY_ID, generate_schedule, rotating_group, schedule_payload, teams_payload, validate_standings
from .playoffs import playoffs_through_round
from .player_stats import aggregate_player_stats
from .leaders import league_leaders
from .simulation import roster_for, simulate_through_week, team_ratings, roster_rules, roster_limit, roster_minimum
from .attributes import ATTRIBUTE_INFO, attribute_keys
from .ratings import rating_payload
from .player_contracts import public_player_fields, payroll_payload, cap_ready, pending_renewals, release_preview, payroll_breakdown, cap_payroll, contract_expired
from .lineups import lineup_context, replace_lineup_rosters
from .simulation import ranked_players
from .draft import build_draft
from .career import offseason, replay_career, prepare_free_agency
from .starter_choices import StarterPlan, with_starters, selected_roster, current_starters


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
                 lineup_rules: Annotated[int, Query(ge=1, le=33)] = 1,
                 season: Annotated[int, Query(ge=1, le=1099)] = 1,
                 development_start: Annotated[int, Query(ge=1, le=1099)] = 1,
                 rebuild_team: Annotated[str | None, Query(max_length=40)] = None) -> dict[str, object]:
    if team_id not in TEAM_BY_ID:
        raise HTTPException(status_code=404, detail="Team not found")
    context = request_lineups(run_seed,lineup_rules,season,development_start,rebuild_team)
    players = list(roster_for(team_id, run_seed, context).values())
    return profile_payload(team_id, players, run_seed, context)


def profile_payload(team_id, players, run_seed, roster_context=(), preferred=(), payroll_season=None, release_previews=False):
    if preferred or getattr(roster_context, 'lineup_rules', 1) >= 2:
        players = selected_roster(players, preferred, fill=True) if preferred else tuple(players) if isinstance(roster_context, StarterPlan) else ranked_players(players)
        rosters = dict(roster_context)
        rosters[team_id] = players
        roster_context = replace_lineup_rosters(roster_context,tuple(rosters.items()))
    development_states = (dict(roster_context.development)
                          if getattr(roster_context, 'lineup_rules', 1) >= 3 else None)
    renewal_payroll = (cap_payroll(players, roster_context, owner=team_id)
                       if getattr(roster_context, 'lineup_rules', 1) >= 23
                       and any(contract_expired(player, roster_context.season) for player in players)
                       else None)
    return {
        "team": asdict(TEAM_BY_ID[team_id]),
        "ratings": asdict(team_ratings(team_id, run_seed, roster_context)),
        "run_seed": run_seed,
        "lineup_rules": getattr(roster_context, "lineup_rules", 1),
        **({"rebuild_team": roster_context.rebuild_team} if getattr(roster_context, "rebuild_team", None) else {}),
        "roster": [{**public_player_fields(player,roster_context,
            development_states=development_states, renewal_payroll=renewal_payroll,
            renewal_owner=team_id),
            **({"release_preview": release_preview(players,player,team_id,payroll_season,run_seed,roster_context)}
               if release_previews and getattr(roster_context,"lineup_rules",1)>=16 else {}), **rating_payload(player,roster_context,development_states), "attributes": {
            key: getattr(player.attributes, key) for key in attribute_keys(player.position)
        }} for player in players],
        "roster_stats": aggregate_player_stats(players, []),
        **payroll_payload(players,roster_context,payroll_season,team_id),
        **payroll_breakdown(players,roster_context,payroll_season,team_id),
        **({"roster_limits": {"minimum": roster_minimum(roster_context), "maximum": roster_limit(roster_context)}} if getattr(roster_context,"lineup_rules",1) >= 13 else {}),
        "roster_rules": [
            {"position": position, "initial": initial, "minimum": minimum,
             "count": sum(player.position == position for player in players),
             "attributes": [
                 {"key": key, "label": ATTRIBUTE_INFO[key][0], "description": ATTRIBUTE_INFO[key][1]}
                 for key in attribute_keys(position)
             ]}
            for position, (initial, minimum) in roster_rules(roster_context).items()
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
    season: int = Query(default=1, ge=1, le=1099),
    prior_standings: Annotated[str | None, Query(max_length=2000)] = None,
    lineup_rules: Annotated[int, Query(ge=1, le=33)] = 1,
    development_start: Annotated[int, Query(ge=1, le=1099)] = 1,
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
    season: int = Query(default=1, ge=1, le=1099),
    run_seed: Annotated[int, Query(ge=0, le=4294967295)] = 0,
    prior_standings: Annotated[str | None, Query(max_length=2000)] = None,
    lineup_rules: Annotated[int, Query(ge=1, le=33)] = 1,
    development_start: Annotated[int, Query(ge=1, le=1099)] = 1,
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
    season: int = Query(default=1, ge=1, le=1099),
    run_seed: Annotated[int, Query(ge=0, le=4294967295)] = 0,
    prior_standings: Annotated[str | None, Query(max_length=2000)] = None,
    lineup_rules: Annotated[int, Query(ge=1, le=33)] = 1,
    development_start: Annotated[int, Query(ge=1, le=1099)] = 1,
    rebuild_team: Annotated[str | None, Query(max_length=40)] = None,
) -> dict[str, object]:
    if team_id not in TEAM_BY_ID:
        raise HTTPException(status_code=404, detail="Team not found")
    if round_number < 0 or round_number > 4:
        raise HTTPException(status_code=400, detail="Playoff round must be between 0 and 4")
    return playoffs_through_round(team_id, season, round_number, run_seed,
                                  parse_prior_standings(prior_standings), request_lineups(run_seed,lineup_rules,season,development_start,rebuild_team))


class DraftRequest(BaseModel):
    draft_rounds: Literal[4, 6] = 4
    season: int = Field(default=1, ge=1, le=1098)
    run_seed: int = Field(default=0, ge=0, le=4294967295)
    lineup_rules: Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33] = 1
    development_start: int = Field(default=1, ge=1, le=1099)
    rebuild_team: str | None = Field(default=None, max_length=40)
    prior_standings: dict[str, StrictInt] | None = None
    manual_picks: list[str] = Field(default_factory=list, max_length=6)
    auto_draft: StrictBool = False


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
                                    tuple(request.manual_picks), prior, context, auto_pick=request.auto_draft, draft_rounds=request.draft_rounds)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {**draft, "profile": profile_payload(team_id, players, request.run_seed, context, payroll_season=request.season+1)}


class LineupChange(BaseModel):
    week: StrictInt = Field(ge=1, le=21)
    starters: list[str] = Field(max_length=22)


class RosterAction(BaseModel):
    kind: Literal['drop','resign','raise']
    player_id: str = Field(min_length=1,max_length=100)


class FreeAgencyAction(BaseModel):
    kind: Literal['sign', 'pass', 'finish', 'resign', 'drop']
    player_id: str = Field(default='', max_length=100)

    @model_validator(mode='after')
    def valid_target(self):
        if (self.kind in ('sign','resign','drop')) != bool(self.player_id):
            raise ValueError('Signings, renewals and releases require a player ID')
        return self


class CareerStep(BaseModel):
    pre_camp_actions: list[RosterAction] = Field(default_factory=list,max_length=128)
    camp_actions: list[RosterAction] = Field(default_factory=list,max_length=128)
    free_agency: list[FreeAgencyAction] = Field(default_factory=list, max_length=256)
    roster_actions: list[RosterAction] = Field(default_factory=list,max_length=132)
    draft_rounds: Literal[4, 6] = 4
    lineup_changes: list[LineupChange] = Field(default_factory=list, max_length=21)
    lineup_rules: Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33] = 1
    season: int = Field(ge=1, le=1098)
    prior_standings: dict[str, StrictInt] | None = None
    manual_picks: list[str] = Field(min_length=4, max_length=6)
    dropped: list[str] = Field(default_factory=list, max_length=44)

    @model_validator(mode='after')
    def complete_draft(self):
        if len(self.manual_picks) != self.draft_rounds:
            raise ValueError('Past offseason must contain one pick per draft round')
        if self.lineup_rules < 31 and (self.pre_camp_actions or self.camp_actions or len(self.free_agency)>24 or any(a.kind in ('resign','drop') for a in self.free_agency)):
            raise ValueError('Pre-camp decisions require the new offseason rules')
        if self.lineup_rules >= 31 and (self.dropped or self.roster_actions):
            raise ValueError('New offseasons use their ordered market and camp decisions')
        if self.free_agency and self.lineup_rules < 29:
            raise ValueError('Legacy offseasons cannot contain free agency decisions')
        if self.roster_actions and self.lineup_rules < 20:
            raise ValueError('Legacy offseasons cannot contain re-signing decisions')
        if self.lineup_rules >= 20 and [a.player_id for a in self.roster_actions if a.kind=='drop'] != self.dropped:
            raise ValueError('Roster actions must preserve the recorded drop order')
        return self


class CareerRequest(BaseModel):
    pre_camp_actions: list[RosterAction] = Field(default_factory=list,max_length=128)
    camp_actions: list[RosterAction] = Field(default_factory=list,max_length=128)
    free_agency: list[FreeAgencyAction] = Field(default_factory=list, max_length=256)
    roster_actions: list[RosterAction] = Field(default_factory=list,max_length=132)
    draft_rounds: Literal[4, 6] = 4
    lineup_changes: list[LineupChange] = Field(default_factory=list, max_length=21)
    action: Literal['profile', 'week', 'playoffs', 'draft', 'camp', 'cuts', 'resign', 'leaders', 'free_agency']
    training_camp: StrictBool = False
    season: int = Field(default=1, ge=1, le=1099)
    run_seed: int = Field(default=0, ge=0, le=4294967295)
    lineup_rules: Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33] = 1
    development_start: int = Field(default=1, ge=1, le=1099)
    rebuild_team: str | None = Field(default=None, max_length=40)
    prior_standings: dict[str, StrictInt] | None = None
    career: list[CareerStep] = Field(default_factory=list, max_length=998)
    manual_picks: list[str] = Field(default_factory=list, max_length=6)
    auto_draft: StrictBool = False
    dropped: list[str] = Field(default_factory=list, max_length=44)
    week: int = Field(default=1, ge=1, le=19)
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
        if request.roster_actions and (request.lineup_rules < 20 or not request.training_camp):
            raise ValueError('Roster decisions are only available after training camp')
        if request.lineup_rules < 31 and request.action == 'resign' and (request.lineup_rules < 20 or not request.training_camp or not request.roster_actions or request.roster_actions[-1].kind != 'resign'):
            raise ValueError('Re-signing requires an expired player after training camp')
        if request.training_camp and request.action == 'draft':
            raise ValueError('The draft is complete once training camp begins')
        if request.action == 'camp' and request.dropped and not request.training_camp:
            raise ValueError('Start training camp before making final cuts')
        if request.auto_draft and (request.action != 'draft' or request.dropped):
            raise ValueError('Auto-draft is only available for an unfinished draft before roster cuts')
        if any(step.season >= request.season for step in request.career):
            raise ValueError('Past offseasons must precede the current season')
        steps = tuple((step.season, ranks_context(step.prior_standings), tuple(step.manual_picks), tuple(step.dropped), step.lineup_rules, tuple((change.week, tuple(change.starters)) for change in step.lineup_changes), step.draft_rounds, tuple((action.kind,action.player_id) for action in step.roster_actions), tuple((a.kind,a.player_id) for a in step.free_agency), tuple((a.kind,a.player_id) for a in step.pre_camp_actions), tuple((a.kind,a.player_id) for a in step.camp_actions))
                      for step in request.career)
        context = replay_career(team_id, request.run_seed, steps, request.lineup_rules,request.season,request.development_start,request.rebuild_team)
        changes = tuple((change.week, tuple(change.starters)) for change in request.lineup_changes)
        context = with_starters(context, team_id, request.run_seed, changes)
        prior = ranks_context(request.prior_standings)
        viewed = request.view_team or team_id
        if request.lineup_rules < 31 and (request.pre_camp_actions or request.camp_actions or len(request.free_agency)>24 or any(a.kind in ('drop','resign') for a in request.free_agency)):
            raise ValueError('Pre-camp decisions require the new offseason rules')
        if request.lineup_rules >= 31 and request.action in ('free_agency','camp','cuts','resign'):
            if request.dropped or request.roster_actions or request.auto_draft:
                raise ValueError('New offseasons require their ordered market and camp logs')
            from .preseason import run
            data, phase_context=run(team_id,request.season,request.run_seed,tuple(request.manual_picks),prior,context,
                request.draft_rounds,tuple((a.kind,a.player_id) for a in request.free_agency),
                tuple((a.kind,a.player_id) for a in request.pre_camp_actions),
                request.training_camp or request.action=='camp',
                tuple((a.kind,a.player_id) for a in request.camp_actions))
            return {**data,'profile':profile_payload(viewed,dict(phase_context)[viewed],request.run_seed,
                phase_context,payroll_season=request.season+1,release_previews=viewed==team_id)}
        if request.free_agency and (request.lineup_rules < 29 or request.action != 'free_agency'):
            raise ValueError('Free agency decisions require the free agency stage')
        if request.action == 'free_agency':
            if request.lineup_rules < 29 or not request.training_camp:
                raise ValueError('Free agency requires completed training camp')
            from .free_agency import free_agency_order
            order = free_agency_order(request.season,request.run_seed,prior,context)
            market_context = prepare_free_agency(team_id, request.season, request.run_seed,
                tuple(request.manual_picks), tuple(request.dropped), prior, context,
                request.draft_rounds, tuple((a.kind,a.player_id) for a in request.roster_actions))
            players = dict(market_context)[team_id]
            if pending_renewals(players,market_context) or len(players)>roster_limit(market_context) or not cap_ready(players,market_context,request.season+1,team_id):
                raise ValueError('Finalize roster cuts and expired contracts before free agency')
            from .free_agency import free_agency
            market, market_context = free_agency(team_id, request.season, request.run_seed,
                market_context, order,
                tuple((a.kind,a.player_id) for a in request.free_agency))
            return {**market, 'team':asdict(TEAM_BY_ID[team_id]), 'season':request.season,
                    'run_seed':request.run_seed,
                    'profile':profile_payload(viewed,dict(market_context)[viewed],request.run_seed,market_context,payroll_season=request.season+1)}
        if request.action == 'leaders':
            return league_leaders(team_id, request.season, request.week, request.run_seed, prior, context)
        if request.action == 'week':
            return simulate_through_week(team_id, request.season, request.week, request.run_seed, prior, context)
        if request.action == 'playoffs':
            return playoffs_through_round(team_id, request.season, request.round_number, request.run_seed, prior, context)
        if request.action in ('draft', 'camp', 'cuts', 'resign'):
            if request.action == 'camp' and request.lineup_rules < 18:
                raise ValueError('Training camp requires the new offseason rules')
            if request.action == 'cuts' and request.lineup_rules >= 18 and not request.training_camp:
                raise ValueError('Start training camp before making final cuts')
            if request.action in ('camp','cuts','resign'):
                draft, cut_context = offseason(team_id, request.season, request.run_seed,
                    tuple(request.manual_picks), tuple(request.dropped), prior, context, request.draft_rounds, tuple((action.kind,action.player_id) for action in request.roster_actions))
                players = list(roster_for(viewed, request.run_seed, cut_context).values())
                return {**draft, 'dropped': request.dropped, 'cuts_applied': True,
                        **({'contracts_pending':pending_renewals(dict(cut_context)[team_id],cut_context)} if request.lineup_rules>=20 else {}),
                        'can_continue': not pending_renewals(dict(cut_context)[team_id],cut_context) and roster_minimum(cut_context) <= len(dict(cut_context)[team_id]) <= roster_limit(cut_context) and cap_ready(dict(cut_context)[team_id],cut_context,request.season+1,team_id),
                        'profile': profile_payload(viewed, players, request.run_seed, cut_context, current_starters(context) if viewed == team_id and request.lineup_rules < 18 else (),payroll_season=request.season+1, release_previews=viewed == team_id)}
            draft, players = build_draft(team_id, request.season, request.run_seed,
                                        tuple(request.manual_picks), prior, context, auto_pick=request.auto_draft, draft_rounds=request.draft_rounds)
            return {**draft, 'profile': profile_payload(team_id, players, request.run_seed, context, payroll_season=request.season+1)}
        return profile_payload(viewed, list(roster_for(viewed, request.run_seed, context).values()), request.run_seed, context)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
