"""Down-and-distance simulation. Attribution uses a separate random stream."""
from collections import Counter
from dataclasses import dataclass, field, replace

from .drives import Totals, clamp, matchup
from .rotation import position_roles, receiving_weights

SNAP_RULES = 52
CALIBRATION_RULES = 53
MATCHUP_SENSITIVITY = .60


def calibrated_matchup(offense, defense, home_edge=0):
    """Scale roster advantages without changing home field or special teams."""
    edge = matchup(offense, defense, home_edge)
    return replace(edge,
                   run=(edge.run - home_edge) * MATCHUP_SENSITIVITY + home_edge,
                   passing=(edge.passing - home_edge) * MATCHUP_SENSITIVITY + home_edge,
                   protection=(edge.protection - home_edge) * MATCHUP_SENSITIVITY + home_edge,
                   run_breakaway=edge.run_breakaway * MATCHUP_SENSITIVITY,
                   pass_breakaway=edge.pass_breakaway * MATCHUP_SENSITIVITY)


@dataclass
class Possession:
    offense: int
    spot: int = 28
    down: int = 1
    to_go: int = 10

    def restart(self, spot):
        self.offense ^= 1
        self.spot, self.down, self.to_go = spot, 1, min(10, 100 - spot)

    def advance(self, yards):
        self.spot += yards
        if yards >= self.to_go:
            self.down, self.to_go = 1, min(10, 100 - self.spot)
        else:
            self.down += 1
            self.to_go -= yards


def play_call(state, edge, half, clock, margin, rng, *, calibrated=False):
    distance = 117 - state.spot
    kick_range = clamp(59 + .24 * (edge.kick_power - 72), 49, 66)
    in_range = distance <= kick_range
    late = half == 1 and clock <= 420
    need_touchdown = late and margin < -3 and clock < 200
    last_chance = clock <= 8
    if state.down == 4 or last_chance:
        short = state.to_go <= 2 and state.spot >= 48
        chase = late and margin < 0 and (clock <= 140 or need_touchdown)
        if last_chance and half == 1 and margin > 0:
            return "run"
        if in_range and (last_chance and not need_touchdown or not (short or chase)):
            return "kick"
        if state.down == 4 and not (short or chase):
            return "kick" if in_range else "punt"
    share = ((.495 if calibrated else .54) + .005 * (edge.passing + .35 * edge.protection - edge.run)
             + .048 * (state.to_go - 7) + .07 * (state.down == 3)
             + .14 * (late and margin < 0) - .17 * (late and margin > 0))
    if state.to_go == 1:
        share -= .17
    return "pass" if rng.random() < clamp(share, .15, .91) else "run"


def rush(rng, edge):
    yards = rng.gauss(3.7 + .075 * edge.run, 3.9)
    if yards > 1 and rng.random() < clamp(.045 * (1 + edge.run / 55), .005, .10):
        yards += clamp(rng.gauss(18 + .5 * edge.run_breakaway, 8), 5, 55)
    return max(-5, round(yards))


def completion(rng, edge, to_go, *, calibrated=False):
    depth = min(15, max(3, to_go))
    yards = rng.gauss(6.25 + .34 * depth + .065 * edge.passing, 5.2)
    breakout = (clamp(.10 + .0009 * edge.pass_breakaway, .02, .20) if calibrated
                else clamp(.045 + .0009 * edge.pass_breakaway, .01, .12))
    if rng.random() < breakout:
        yards += clamp(rng.gauss(22 + .45 * edge.pass_breakaway, 9), 5, 55)
    return max(-3, round(yards))


@dataclass
class TeamStats(Totals):
    safeties: int = 0


@dataclass
class Credits:
    rushers: dict = field(default_factory=dict)
    receivers: dict = field(default_factory=dict)
    sacks: Counter = field(default_factory=Counter)
    interceptions: Counter = field(default_factory=Counter)


class Participants:
    def __init__(self, roster):
        players = list(roster.values())
        roles = position_roles(players, "RB")
        self.backs = (list(roles), list(roles.values()))
        self.targets = (list(roles), [.18 * role for role in roles.values()])
        for position, share in (("WR", .60), ("TE", .22)):
            group, weights = receiving_weights(players, position, share)
            self.targets[0].extend(p.id for p in group)
            self.targets[1].extend(weights)
        self.sack = self.defenders(players, {"DL": 6, "LB": 3})
        self.interception = self.defenders(players, {"LB": 1, "CB": 3, "S": 3})

    @staticmethod
    def defenders(players, weights):
        roles = {identity: role for position in weights
                 for identity, role in position_roles(players, position).items()}
        candidates = [p for p in players if p.id in roles]
        return ([p.id for p in candidates],
                [roles[p.id] * p.rating * weights[p.position] for p in candidates])


def credit(stats_rng, participants, credits, offense, event, yards, touchdown):
    attack, defense = participants[offense], participants[offense ^ 1]
    own, other = credits[offense], credits[offense ^ 1]
    if event == "run":
        player = stats_rng.choices(*attack.backs)[0]
        row = own.rushers.setdefault(player, Counter())
        row.update(attempts=1, yards=yards, touchdowns=int(touchdown))
    elif event == "sack":
        other.sacks[stats_rng.choices(*defense.sack)[0]] += 1
    else:
        player = stats_rng.choices(*attack.targets)[0]
        row = own.receivers.setdefault(player, Counter())
        row["targets"] += 1
        if event == "complete":
            row.update(receptions=1, yards=yards, touchdowns=int(touchdown))
        elif event == "interception":
            other.interceptions[stats_rng.choices(*defense.interception)[0]] += 1


def simulate(rng, home, away, *, neutral_site=False, stats_rng=None, rules=SNAP_RULES):
    calibrated = rules >= CALIBRATION_RULES
    compare = calibrated_matchup if calibrated else matchup
    edges = (compare(home, away, 0 if neutral_site else 1.6), compare(away, home))
    normal_seconds, hurry_seconds, protect_seconds, stopped_seconds, punt_seconds, kick_seconds = (
        (37, 19, 40, 10, 15, 12) if calibrated else (32, 17, 37, 7, 8, 5))
    base_completion = .650 if calibrated else .610
    totals = (TeamStats(), TeamStats())
    credits = (Credits(), Credits()) if stats_rng is not None else (None, None)
    if stats_rng is not None:
        participants = (Participants(home), Participants(away))
    first = rng.randrange(2)
    for half in range(2):
        state = Possession(first ^ half)
        clock = 1800
        while clock:
            offense = state.offense
            team, opponent = totals[offense], totals[offense ^ 1]
            edge = edges[offense]
            margin = team.score - opponent.score
            call = play_call(state, edge, half, clock, margin, rng, calibrated=calibrated)
            if call == "punt":
                team.seconds += min(punt_seconds, clock)
                clock = max(0, clock - punt_seconds)
                landing = state.spot + rng.randint(32, 49)
                state.restart(20 if landing >= 100 else 100 - landing)
                continue
            if call == "kick":
                distance = 117 - state.spot
                made = rng.random() < clamp(.96 - .013 * max(0, distance - 32)
                                            + .006 * (edge.kick_accuracy - 72), .22, .995)
                team.kicks.append((distance, made))
                team.score += 3 * made
                team.seconds += min(kick_seconds, clock)
                clock = max(0, clock - kick_seconds)
                state.restart(28 if made else clamp(107 - state.spot, 20, 99))
                continue

            turnover, yards = False, 0
            if call == "run":
                team.carries += 1
                event, yards = "run", rush(rng, edge)
                turnover = rng.random() < clamp(.008 - .00018 * (edge.ball_security - 72), .002, .025)
            elif rng.random() < clamp(.061 - .0017 * edge.protection, .023, .16):
                team.sacks += 1
                event, yards = "sack", -rng.randint(3, 9)
            else:
                team.attempts += 1
                roll = rng.random()
                pick = clamp(.022 - .00055 * edge.passing, .008, .055)
                complete = clamp(base_completion + .0048 * edge.passing + .0012 * edge.protection
                                 - .007 * max(0, state.to_go - 8), .37, .84)
                if roll < pick:
                    event, turnover = "interception", True
                    team.interceptions += 1
                elif roll < pick + complete:
                    event, yards = "complete", completion(rng, edge, state.to_go, calibrated=calibrated)
                    team.completions += 1
                else:
                    event = "incomplete"

            yards = clamp(yards, -state.spot, 100 - state.spot)
            touchdown = state.spot + yards == 100 and not turnover
            if event == "run":
                team.rushing_yards += yards
                team.rushing_tds += int(touchdown)
                team.fumbles += int(turnover)
            elif event == "complete":
                team.passing_yards += yards
                team.passing_tds += int(touchdown)
            if stats_rng is not None:
                credit(stats_rng, participants, credits, offense, event, yards, touchdown)

            hurry = (half == 0 and clock < 125) or (half == 1 and clock < 380 and margin < 0)
            protect = half == 1 and clock < 380 and margin > 0
            elapsed = stopped_seconds if event in ("incomplete", "interception") or touchdown or turnover else (
                hurry_seconds if hurry else protect_seconds if protect else normal_seconds)
            elapsed = min(clock, elapsed)
            team.seconds += elapsed
            clock -= elapsed
            state.advance(yards)
            if touchdown:
                team.score += 7
                state.restart(28)
            elif state.spot == 0:
                opponent.score += 2
                opponent.safeties += 1
                state.restart(35)
            elif turnover or state.down == 5:
                spot = 20 if state.spot == 100 else 100 - state.spot
                state.restart(spot)
    return totals, credits
