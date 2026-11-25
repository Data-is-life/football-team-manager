"""Coach decisions based on down, yards to go, and field position."""

from bisect import bisect_left

from .drives import clamp


# Columns are 1, 2–3, 4–6, 7–10, and 11+ yards to go.
# Fit to close games with more than seven minutes left in the half.
OPEN_FIELD_PASS_SHARE = (
    (.18, .28, .38, .44, .65),
    (.24, .32, .47, .63, .79),
    (.23, .67, .89, .91, .86),
    (.23, .78, .85, .90, .91),
)
RED_ZONE_PASS_SHARE = (
    (.13, .22, .28, .34, .45),
    (.18, .30, .49, .67, .70),
    (.23, .64, .87, .92, .85),
    (.26, .76, .88, .90, .91),
)

# Rows run from deep in the offense's territory to the opponent's red zone.
FOURTH_DOWN_GO_SHARE = (
    (.11, .03, .01, .005, .005),  # Own 1–29
    (.34, .03, .02, .01, .005),   # Own 30–39
    (.63, .13, .04, .02, .005),   # Own 40–49
    (.91, .57, .18, .03, .005),   # Midfield to opponent's 41
    (.84, .50, .16, .03, .01),    # Opponent's 40–21
    (.85, .35, .06, .01, .005),   # Opponent's 20–1
)


DISTANCE_LIMITS = (1, 3, 6, 10)
FIELD_LIMITS = (29, 39, 49, 59, 79)


def fourth_down_call(state, edge, half, clock, margin, rng, band,
                     *, short_yardage=False):
    """Return a kick, punt, or None to keep the offense on the field."""
    kick_distance = 117 - state.spot - .24 * (edge.kick_power - 72)
    if half == 1 and clock <= 140 and margin < 0:
        if margin >= -3 and kick_distance <= 57:
            return "kick"
        return None

    field_band = bisect_left(FIELD_LIMITS, state.spot)
    go_share = FOURTH_DOWN_GO_SHARE[field_band][band]
    if short_yardage and band == 0:
        go_share += .30 * (1 - go_share)
    # Matchup shifts are bounded so they cannot swamp field position.
    conversion_edge = (
        edge.run if band == 0 else edge.passing + .35 * edge.protection
    )
    matchup_adjustment = clamp(.02 * conversion_edge, -.4, .4)
    go_share += go_share * (1 - go_share) * matchup_adjustment
    if margin < -8:
        if half == 0:
            aggression = .05
        else:
            aggression = .65 if clock <= 420 else .22
        go_share += aggression * (1 - go_share)
    elif half == 1 and clock <= 420:
        if margin < 0:
            go_share += .32 * (1 - go_share)
        elif margin > 0:
            go_share *= .65
    if rng.random() < go_share:
        return None

    # The kick probability drops sharply near the edge of field goal range.
    if kick_distance <= 52:
        return "kick"
    if kick_distance <= 57 and rng.random() < .67:
        return "kick"
    if 57 < kick_distance <= 62 and rng.random() < .04:
        return "kick"
    return "punt"


def play_call(state, edge, half, clock, margin, rng, *, short_yardage=False):
    band = bisect_left(DISTANCE_LIMITS, state.to_go)
    if clock <= 8:
        if half == 1 and margin > 0:
            return "run"
        in_range = 117 - state.spot <= clamp(
            59 + .24 * (edge.kick_power - 72), 49, 66
        )
        if in_range and (half == 0 or margin >= -3):
            return "kick"
    if state.down == 4:
        decision = fourth_down_call(
            state, edge, half, clock, margin, rng, band,
            short_yardage=short_yardage,
        )
        if decision is not None:
            return decision

    pass_shares = (
        RED_ZONE_PASS_SHARE if state.spot >= 80 else OPEN_FIELD_PASS_SHARE
    )
    share = pass_shares[state.down - 1][band]
    share += .005 * (edge.passing + .35 * edge.protection - edge.run)
    if half == 1 and clock <= 420:
        share += .14 * (margin < 0) - .17 * (margin > 0)
    return "pass" if rng.random() < clamp(share, .08, .97) else "run"
