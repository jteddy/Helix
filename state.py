"""
core/state.py
-------------
Single source of truth shared between the recoil loop and the web API.

The recoil loop reads from this object every iteration.
The web API writes to this object when the user changes settings.
A threading.Lock protects all reads and writes.

Usage:
    from core.state import state

    # Read
    with state.lock:
        enabled = state.enabled
        vectors = list(state.vectors)

    # Write
    with state.lock:
        state.enabled = True
        state.scalar = 1.5
"""

import threading
from dataclasses import dataclass, field


@dataclass
class RecoilState:
    # ── Recoil settings ───────────────────────────────────────────────────────
    enabled:          bool  = False
    vectors:          list  = field(default_factory=list)  # [(x, y, delay_s), ...]
    scalar:           float = 1.0
    x_control:        float = 1.0
    y_control:        float = 1.0
    loop_recoil:      bool  = False
    require_aim:      bool  = False   # require RMB held to activate
    return_crosshair: bool  = False
    return_speed:     float = 0.5
    randomisation:    bool  = False
    rand_strength:    float = 0.5

    # ── Sensitivity / game scaling ────────────────────────────────────────────
    # If game is set to a known game, scalar is derived from base/user_sensitivity.
    # If game is "Manual", scalar is used directly.
    game:             str   = "Manual"
    sensitivity:      float = 1.0

    # ── Active pattern info (display only) ───────────────────────────────────
    active_game:      str   = ""
    active_weapon:    str   = ""

    # ── MAKCU status (written by device layer, read by WebSocket) ─────────────
    makcu_connected:  bool  = False

    # ── Recoil loop status (written by loop, read by WebSocket) ───────────────
    recoil_active:    bool  = False   # True when LMB held and firing


class _State:
    """
    Thread-safe wrapper around RecoilState.
    Use `with state.lock:` before reading or writing any field.
    """
    def __init__(self):
        self._data = RecoilState()
        self.lock  = threading.Lock()

    def __getattr__(self, name):
        if name in ('lock', '_data'):
            return object.__getattribute__(self, name)
        return getattr(self._data, name)

    def __setattr__(self, name, value):
        if name in ('lock', '_data'):
            object.__setattr__(self, name, value)
        else:
            setattr(self._data, name, value)

    def to_dict(self) -> dict:
        """Return all settings as a plain dict (for API responses)."""
        d = self._data.__dict__.copy()
        # Convert vectors to serialisable format
        d['vectors'] = [
            {'x': v[0], 'y': v[1], 'ms': int(v[2] * 1000)}
            for v in (self._data.vectors or [])
        ]
        return d

    def load_vectors_from_txt(self, text: str):
        """
        Parse x,y,ms lines from a .txt vector file and store as
        (x, y, delay_seconds) tuples ready for the recoil loop.
        """
        vectors = []
        for line in text.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                parts = line.split(',')
                x   = float(parts[0])
                y   = float(parts[1])
                ms  = float(parts[2])
                vectors.append((x, y, ms / 1000.0))
            except (ValueError, IndexError):
                pass
        with self.lock:
            self._data.vectors = vectors
        return len(vectors)


# ── Singleton ─────────────────────────────────────────────────────────────────
# Import this everywhere:  from core.state import state
state = _State()
