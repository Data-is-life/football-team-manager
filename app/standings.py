from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from .league import GROUPS, TEAM_BY_ID, TEAMS
from .simulation import _run_number, league_week_scores


@dataclass
class TeamStanding:
    team_id: str
    wins: int = 0
    losses: int = 0
    ties: int = 0
    points_for: int = 0
    points_against: int = 0
    group_wins: int = 0
    group_losses: int = 0
    group_ties: int = 0
    opponents: list[tuple[str, str]] = field(default_factory=list)

    @property
    def standings_points(self) -> int:
        return self.wins * 2 + self.ties

    @property
    def point_differential(self) -> int:
        return self.points_for - self.points_against

    @property
    def record(self) -> str:
        return f"{self.wins}-{self.losses}" + (f"-{self.ties}" if self.ties else "")


def _apply_result(
    standing: TeamStanding,
    opponent_id: str,
    points_for: int,
    points_against: int,
) -> None:
    if points_for > points_against:
        outcome = "W"
        standing.wins += 1
    elif points_for < points_against:
        outcome = "L"
        standing.losses += 1
    else:
        outcome = "T"
        standing.ties += 1
    standing.points_for += points_for
    standing.points_against += points_against
    standing.opponents.append((opponent_id, outcome))

    if TEAM_BY_ID[standing.team_id].group == TEAM_BY_ID[opponent_id].group:
        if outcome == "W":
            standing.group_wins += 1
        elif outcome == "L":
            standing.group_losses += 1
        else:
            standing.group_ties += 1


def _record_score(standing: TeamStanding, opponents: set[str]) -> float:
    games = [outcome for opponent, outcome in standing.opponents if opponent in opponents]
    if not games:
        return -1.0
    return (games.count("W") + games.count("T") * 0.5) / len(games)


def _rank_teams(
    team_ids: list[str],
    standings: dict[str, TeamStanding],
    season: int,
    run_seed: int = 0,
) -> list[str]:
    by_record: dict[int, list[str]] = {}
    for team_id in team_ids:
        by_record.setdefault(standings[team_id].standings_points, []).append(team_id)

    ranked: list[str] = []
    for record_points in sorted(by_record, reverse=True):
        cohort = by_record[record_points]
        cohort_set = set(cohort)
        opponent_sets = [
            {opponent for opponent, _ in standings[team_id].opponents} - cohort_set
            for team_id in cohort
        ]
        common_opponents = set.intersection(*opponent_sets) if opponent_sets else set()
        random_context = ":".join(sorted(cohort))

        cohort.sort(
            key=lambda team_id: (
                _record_score(standings[team_id], cohort_set - {team_id}),
                _record_score(standings[team_id], common_opponents),
                standings[team_id].point_differential,
                standings[team_id].points_for,
                _run_number(f"tiebreak:{season}:{random_context}:{team_id}", run_seed),
            ),
            reverse=True,
        )
        ranked.extend(cohort)
    return ranked


def _standing_payload(standing: TeamStanding, rank: int) -> dict[str, object]:
    team = TEAM_BY_ID[standing.team_id]
    return {
        "rank": rank,
        "team": {"id": team.id, "city": team.city, "group": team.group},
        "record": standing.record,
        "wins": standing.wins,
        "losses": standing.losses,
        "ties": standing.ties,
        "points_for": standing.points_for,
        "points_against": standing.points_against,
        "point_differential": standing.point_differential,
        "group_record": f"{standing.group_wins}-{standing.group_losses}"
        + (f"-{standing.group_ties}" if standing.group_ties else ""),
    }


@lru_cache(maxsize=128)
def standings_through_week(season: int, week: int, run_seed: int = 0) -> dict[str, object]:
    if week < 1 or week > 17:
        raise ValueError("Week must be between 1 and 17")
    standings = {team.id: TeamStanding(team_id=team.id) for team in TEAMS}

    for completed_week in range(1, week + 1):
        for home_id, away_id, home_score, away_score in league_week_scores(season, completed_week, run_seed):
            _apply_result(
                standings[home_id], away_id, home_score, away_score,
            )
            _apply_result(
                standings[away_id], home_id, away_score, home_score,
            )

    group_tables: list[dict[str, object]] = []
    group_winners: list[str] = []
    for group, cities in GROUPS.items():
        team_ids = [team.id for team in TEAMS if team.group == group]
        ranked = _rank_teams(team_ids, standings, season, run_seed)
        group_winners.append(ranked[0])
        group_tables.append({
            "group": group,
            "teams": [_standing_payload(standings[team_id], rank) for rank, team_id in enumerate(ranked, 1)],
        })

    seeded_group_winners = _rank_teams(group_winners, standings, season, run_seed)
    wildcard_pool = [team.id for team in TEAMS if team.id not in set(group_winners)]
    wildcards = _rank_teams(wildcard_pool, standings, season, run_seed)[:8]
    playoff_ids = [*seeded_group_winners, *wildcards]
    playoff_race = []
    for seed, team_id in enumerate(playoff_ids, start=1):
        row = _standing_payload(standings[team_id], seed)
        row.update({
            "seed": seed,
            "qualification": "Group winner" if seed <= 6 else "Wildcard",
            "bye": seed <= 2,
        })
        playoff_race.append(row)

    return {
        "week": week,
        "groups": group_tables,
        "playoff_race": playoff_race,
        "tiebreakers": [
            "Head-to-head",
            "Common-opponent record",
            "Point differential",
            "Points scored",
            "Deterministic random draw",
        ],
    }
