"""Exclude additive display metadata from pre-existing gameplay snapshots."""
def without_rookie_origin(fields):
    return {key:value for key,value in fields.items() if key != 'rookie_origin'}
