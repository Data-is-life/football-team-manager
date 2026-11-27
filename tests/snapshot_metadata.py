"""Exclude additive display metadata from pre-existing gameplay snapshots."""

DISPLAY_METADATA = {"rookie_origin", "draft_pick", "height_inches", "weight_lbs"}


def without_display_metadata(fields):
    return {key: value for key, value in fields.items() if key not in DISPLAY_METADATA}
