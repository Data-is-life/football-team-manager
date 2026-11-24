"""Supported save-rule versions shared by request and simulation validation."""
from typing import Literal

MAX_LINEUP_RULES = 54
SUPPORTED_RULES = tuple(range(1, MAX_LINEUP_RULES + 1))
DEVELOPMENT_RULES = SUPPORTED_RULES[2:]
LineupRules = Literal[*SUPPORTED_RULES]
