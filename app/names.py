"""Load the bundled name pools once, without a runtime network dependency."""

from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent / "data"


def load_names(path: Path) -> tuple[str, ...]:
    names = []
    seen = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        name = line.strip()
        if not name or name.startswith("#"):
            continue
        if name.casefold() not in seen:
            names.append(name)
            seen.add(name.casefold())
    if not names:
        raise ValueError(f"Name pool is empty: {path.name}")
    return tuple(names)


FIRST_NAMES = load_names(DATA_DIR / "first_names.txt")
LAST_NAMES = load_names(DATA_DIR / "last_names.txt")
