"""Seeded possession simulation, with one aggregate draw per drive."""
from dataclasses import dataclass, field
from math import sqrt

from .rotation import SLOTS

DRIVE_RULES = 51


def clamp(value, low, high):
    return max(low, min(high, value))


def skills(roster, position, *attributes):
    """Current ratings and attributes carry development and decline into games."""
    grades = []
    for p in roster.values():
        if p.position == position:
            values = [getattr(p.attributes, name) for name in attributes]
            grades.append(.25 * p.rating + .75 * sum(p.rating if v is None else v for v in values) / len(values))
    slots = SLOTS[position]
    first, reserves = grades[:slots], grades[slots:]
    if not first:
        return 45
    primary = sum(first) / len(first)
    return .9 * primary + .1 * sum(reserves) / len(reserves) if reserves and position != "K" else primary


@dataclass(frozen=True)
class Matchup:
    run: float
    run_breakaway: float
    passing: float
    protection: float
    pass_breakaway: float
    ball_security: float
    kick_accuracy: float
    kick_power: float


def matchup(offense, defense, home_edge=0):
    g = skills
    front = .72 * g(defense, "DL", "strength", "tackling") + .28 * g(defense, "LB", "strength", "tackling")
    run = .65 * g(offense, "OL", "run_blocking", "strength") + .35 * g(offense, "RB", "agility", "strength")
    pursuit = .72 * g(defense, "S", "speed", "tackling") + .28 * g(defense, "LB", "speed", "tackling")
    coverage = .68 * g(defense, "CB", "coverage", "agility") + .32 * g(defense, "S", "coverage", "iq")
    passing = (.52 * g(offense, "QB", "accuracy", "iq") + .34 * g(offense, "WR", "route_running", "catching")
               + .14 * g(offense, "TE", "catching", "route_running"))
    pressure = .80 * g(defense, "DL", "pass_rush", "strength") + .20 * g(defense, "LB", "speed", "strength")
    deep_offense = .55 * g(offense, "QB", "arm_strength", "accuracy") + .45 * g(offense, "WR", "speed", "route_running")
    deep_defense = .67 * g(defense, "S", "speed", "coverage") + .33 * g(defense, "CB", "speed", "coverage")
    return Matchup(run-front+home_edge, g(offense, "RB", "speed", "agility")-pursuit,
                   passing-coverage+home_edge, g(offense, "OL", "pass_blocking")-pressure+home_edge,
                   deep_offense-deep_defense, g(offense, "RB", "ball_security"),
                   g(offense, "K", "kick_accuracy"), g(offense, "K", "kick_power"))


def yardage(rng, opportunities, edge, deep_edge, through_air):
    if not opportunities:
        return 0
    baseline, spread = (9.8, 7.0) if through_air else (4.2, 4.5)
    ordinary = rng.gauss(opportunities * clamp(baseline + .075 * edge, 1, 14), spread * sqrt(opportunities))
    breakout = clamp((.029 if through_air else .022) * opportunities * (1 + edge / 55), .004, .38)
    if rng.random() < breakout:
        ordinary += clamp(rng.gauss(28 + .55 * deep_edge, 9), 7, 65)
    return max(0, round(ordinary))


@dataclass
class Totals:
    score: int = 0
    seconds: int = 0
    attempts: int = 0
    completions: int = 0
    passing_yards: int = 0
    passing_tds: int = 0
    carries: int = 0
    rushing_yards: int = 0
    rushing_tds: int = 0
    interceptions: int = 0
    fumbles: int = 0
    sacks: int = 0
    kicks: list = field(default_factory=list)


def simulate(rng, home, away, *, neutral_site=False):
    edges = (matchup(home, away, 0 if neutral_site else 1.6), matchup(away, home))
    totals = (Totals(), Totals())
    first = rng.randrange(2)
    for half in range(2):
        offense = first ^ half
        clock, start = 1800, 28
        while clock:
            team, opponent = totals[offense], totals[offense ^ 1]
            edge = edges[offense]
            margin = team.score - opponent.score
            late = half == 1 and clock < 480
            hurry = (late and margin < 0) or (half == 0 and clock < 120)
            protect = late and margin > 0
            share = clamp(.60 + .005 * (edge.passing + .35 * edge.protection - edge.run)
                          + .16 * hurry - .16 * protect, .26, .82)
            quality = share * (edge.passing + .30 * edge.protection) + (1-share) * edge.run
            plays = clamp(round(rng.gauss(5.8 + .055 * quality, 2.7)), 3, 13)
            pace = 17 if hurry else 36 if protect else 27
            plays = min(plays, (clock + pace - 1) // pace)
            elapsed = min(clock, plays * pace)
            passes = clamp(round(plays * share + rng.gauss(0, 1)), 0, plays)
            carries = plays - passes
            sacks = int(passes > 0 and rng.random() < clamp(passes * (.065 - .002 * edge.protection), .015, .50))
            attempts = passes - sacks
            interception = int(attempts > 0 and rng.random() < clamp(attempts * (.024 - .00065 * edge.passing), .005, .23))
            fumble = int(not interception and carries > 0 and rng.random() < clamp(carries * (.012 - .00022 * (edge.ball_security-72)), .003, .10))
            rate = clamp(.64 + .004 * edge.passing + .0015 * edge.protection, .40, .83)
            completions = clamp(round((attempts-interception) * rate + rng.gauss(0, .55)), 0, attempts-interception)
            air = yardage(rng, completions, edge.passing, edge.pass_breakaway, True)
            ground = yardage(rng, carries, edge.run, edge.run_breakaway, False)
            goal = 100 - start
            advance = air + ground
            short_of_goal = goal - advance
            # Fold red-zone execution into the drive outcome before assigning its yards.
            finish = (0 < short_of_goal <= 20 and plays >= 3
                      and rng.random() < clamp(.78 - .022 * short_of_goal + .004 * quality, .16, .87))
            touchdown = (short_of_goal <= 0 or finish) and not (interception or fumble)
            gained = goal if touchdown else min(goal - 1, advance)
            air = round(gained * air / advance) if advance else 0
            ground = gained - air
            end = start + gained

            team.seconds += elapsed
            team.attempts += attempts
            team.completions += completions
            team.passing_yards += air
            team.carries += carries
            team.rushing_yards += ground
            team.sacks += sacks
            team.interceptions += interception
            team.fumbles += fumble
            clock -= elapsed
            if touchdown:
                pass_td = bool(completions and (not carries or rng.random() < air/gained))
                team.passing_tds += int(pass_td)
                team.rushing_tds += int(not pass_td)
                team.score += 7
                start = 28
            elif interception or fumble:
                start = 100 - end
            elif (distance := 117 - end) <= clamp(59 + .24 * (edge.kick_power-72), 49, 66) and (
                    not hurry or margin >= -3 or clock > 120):
                made = rng.random() < clamp(.94 - .012 * max(0, distance-32) + .006 * (edge.kick_accuracy-72), .25, .99)
                team.kicks.append((distance, made))
                team.score += 3 * made
                start = 28 if made else min(99, 107-end)
            else:
                net = rng.randint(30, 45)
                start = 20 if end + net >= 100 else 100 - end - net
            offense ^= 1
    return totals
