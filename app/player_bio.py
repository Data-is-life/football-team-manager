"""Stable, position-specific measurements for fictional player profiles."""

from hashlib import sha256


# Inclusive height (inches) and weight (pounds) ranges.
MEASUREMENT_RANGES = {
    "QB": ((71, 79), (195, 244)),
    "RB": ((67, 74), (185, 239)),
    "WR": ((68, 78), (170, 231)),
    "TE": ((73, 80), (225, 270)),
    "OL": ((73, 81), (285, 350)),
    "DL": ((72, 79), (250, 340)),
    "LB": ((70, 77), (218, 265)),
    "CB": ((68, 76), (175, 214)),
    "S": ((69, 77), (185, 225)),
    "K": ((68, 77), (170, 218)),
}


def player_measurements(player_id: str, position: str, run_seed: int) -> dict:
    """Generate display values independently of the simulation's RNG."""
    height_range, weight_range = MEASUREMENT_RANGES[position]
    digest = sha256(f"player-bio-v1:{run_seed}:{player_id}".encode()).digest()
    height_min, height_max = height_range
    weight_min, weight_max = weight_range
    height = height_min + digest[0] % (height_max - height_min + 1)
    weight = weight_min + int.from_bytes(digest[1:3], "big") % (
        weight_max - weight_min + 1
    )
    return {"height_inches": height, "weight_lbs": weight}
