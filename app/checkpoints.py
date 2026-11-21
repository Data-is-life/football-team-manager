"""Portable season-start state. The browser stores the token; the server owns it."""
import base64
from collections import OrderedDict
from dataclasses import asdict
from decimal import Decimal
import hashlib
import json
import os
from threading import Lock
import zlib

from cryptography.fernet import Fernet, InvalidToken

from .attributes import PlayerAttributes
from .development import DevelopmentState, SimpleDevelopmentContext
from .player_contracts import DeadCapCharge, PlayerContract
from .simulation import Player

# Bump when saved state or the deterministic reconstruction rules change.
CHECKPOINT_VERSION = 1
MAX_TOKEN_LENGTH = 512 * 1024
MAX_STATE_BYTES = 4 * 1024 * 1024
_secret = os.environ.get("CAREER_CHECKPOINT_SECRET")
_cipher = Fernet(base64.urlsafe_b64encode(hashlib.sha256(_secret.encode()).digest())
                 if _secret else Fernet.generate_key())
_restored = OrderedDict()
_lock = Lock()


def _binding(career_key):
    canonical = json.dumps(career_key, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def encode_checkpoint(career_key, context):
    if type(context) is not SimpleDevelopmentContext:
        return None
    data = asdict(context)
    data["salary_anchors"] = [(position, str(rating)) for position, rating in context.salary_anchors]
    state = json.dumps([CHECKPOINT_VERSION, _binding(career_key), data],
                       separators=(",", ":")).encode()
    if len(state) > MAX_STATE_BYTES:
        return None
    token = _cipher.encrypt(zlib.compress(state)).decode("ascii")
    return token if len(token) <= MAX_TOKEN_LENGTH else None


def _player(data):
    return Player(**{
        **data,
        "attributes": PlayerAttributes(**data["attributes"]),
        "contract": PlayerContract(**data["contract"]) if data["contract"] else None,
        "rookie_offer": PlayerContract(**data["rookie_offer"]) if data["rookie_offer"] else None,
    })


def _decode_checkpoint(career_key, token):
    if not token or len(token) > MAX_TOKEN_LENGTH:
        return None
    try:
        compressed = _cipher.decrypt(token.encode("ascii"))
        inflater = zlib.decompressobj()
        raw = inflater.decompress(compressed, MAX_STATE_BYTES + 1)
        if not inflater.eof or len(raw) > MAX_STATE_BYTES:
            return None
        version, binding, data = json.loads(raw)
        if version != CHECKPOINT_VERSION or binding != _binding(career_key):
            return None
        return SimpleDevelopmentContext(**{
            **data,
            "rosters": tuple((owner, tuple(map(_player, players))) for owner, players in data["rosters"]),
            "development": tuple((identity, DevelopmentState(**state)) for identity, state in data["development"]),
            "dead_cap": tuple(DeadCapCharge(**charge) for charge in data["dead_cap"]),
            "free_agents": tuple(map(_player, data["free_agents"])),
            "salary_anchors": tuple((position, Decimal(rating)) for position, rating in data["salary_anchors"]),
            "free_agent_entries": tuple(map(tuple, data["free_agent_entries"])),
        })
    except (InvalidToken, UnicodeError, ValueError, TypeError, KeyError, zlib.error):
        return None


def remember_context(career_key, context):
    with _lock:
        _restored[career_key] = context
        _restored.move_to_end(career_key)
        if len(_restored) > 8:
            _restored.popitem(last=False)


def restored_context(career_key, token=None):
    """Share a verified context with the week, playoff, and offseason requests."""
    context = _decode_checkpoint(career_key, token)
    if context is not None:
        remember_context(career_key, context)
        return context, True
    with _lock:
        context = _restored.get(career_key)
        if context is not None:
            _restored.move_to_end(career_key)
        return context, False
