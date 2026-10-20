"""Deterministic scouting attributes, reserved for the future game engine."""

from dataclasses import dataclass
import hashlib


COMMON_ATTRIBUTES = ("iq", "speed", "durability")
POSITION_ATTRIBUTES = {
    "QB": ("accuracy", "arm_strength", "clutch"),
    "WR": ("catching", "route_running", "strength"), "TE": ("catching", "route_running", "strength"),
    "RB": ("strength", "agility", "ball_security"),
    "OL": ("strength", "pass_blocking", "run_blocking"),
    "DL": ("strength", "pass_rush", "tackling"), "LB": ("strength", "tackling", "coverage"),
    "CB": ("agility", "coverage", "tackling"), "S": ("agility", "coverage", "tackling"),
    "K": ("kick_accuracy", "kick_power"),
}
ATTRIBUTE_INFO = {
    "iq": ("Football IQ", "Reading the game, positioning, and decision-making."),
    "speed": ("Speed", "Straight-line movement speed."),
    "durability": ("Durability", "Resistance to injury."),
    "accuracy": ("Accuracy", "Placing passes on target."),
    "arm_strength": ("Arm Strength", "Throwing power and range."),
    "clutch": ("Clutch Factor", "Composure in high-pressure situations."),
    "catching": ("Catching", "Securing the ball on a reception."),
    "route_running": ("Route Running", "Running precise routes and creating separation."),
    "strength": ("Strength", "Physical power in contact."),
    "agility": ("Agility", "Changing direction and making cuts."),
    "ball_security": ("Ball Security", "Protecting the ball through contact and avoiding fumbles."),
    "pass_blocking": ("Pass Blocking", "Protecting the passer from pressure."),
    "run_blocking": ("Run Blocking", "Opening running lanes for the ball carrier."),
    "pass_rush": ("Pass Rush", "Beating pass protection to pressure the quarterback."),
    "tackling": ("Tackling", "Bringing the ball carrier down."),
    "coverage": ("Coverage", "Staying with receivers and defending passes."),
    "kick_accuracy": ("Kick Accuracy", "Placing kicks on target."),
    "kick_power": ("Kick Power", "Kicking range and distance."),
}


@dataclass(frozen=True)
class PlayerAttributes:
    iq: int
    speed: int
    durability: int
    accuracy: int | None = None
    arm_strength: int | None = None
    clutch: int | None = None
    catching: int | None = None
    route_running: int | None = None
    strength: int | None = None
    agility: int | None = None
    ball_security: int | None = None
    pass_blocking: int | None = None
    run_blocking: int | None = None
    pass_rush: int | None = None
    tackling: int | None = None
    coverage: int | None = None
    kick_accuracy: int | None = None
    kick_power: int | None = None


def attribute_keys(position: str) -> tuple[str, ...]:
    return COMMON_ATTRIBUTES + POSITION_ATTRIBUTES[position]


def generate_attributes(player_id: str, position: str, rating: int) -> PlayerAttributes:
    values = {}
    for key in attribute_keys(position):
        seed = hashlib.sha256(f"{player_id}:attribute:{key}".encode("utf-8")).digest()
        offset = int.from_bytes(seed[:8], "big") % 37 - 18
        values[key] = max(1, min(99, rating + offset))
    return PlayerAttributes(**values)
