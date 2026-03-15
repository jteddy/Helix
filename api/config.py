"""
api/config.py
-------------
REST endpoints for reading and writing recoil settings.
All reads/writes go through the shared state singleton.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from core.state import state

router = APIRouter(prefix="/api/config", tags=["config"])


# ── Models ────────────────────────────────────────────────────────────────────

class ConfigUpdate(BaseModel):
    enabled:          Optional[bool]  = None
    scalar:           Optional[float] = None
    x_control:        Optional[float] = None
    y_control:        Optional[float] = None
    loop_recoil:      Optional[bool]  = None
    require_aim:      Optional[bool]  = None
    return_crosshair: Optional[bool]  = None
    return_speed:     Optional[float] = None
    randomisation:    Optional[bool]  = None
    rand_strength:    Optional[float] = None
    game:             Optional[str]   = None
    sensitivity:      Optional[float] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
def get_config():
    """Return all current recoil settings."""
    return state.to_dict()


@router.patch("")
def update_config(update: ConfigUpdate):
    """
    Update one or more recoil settings.
    Only fields that are not None are applied.
    """
    with state.lock:
        if update.enabled          is not None: state.enabled          = update.enabled
        if update.scalar           is not None: state.scalar           = update.scalar
        if update.x_control        is not None: state.x_control        = update.x_control
        if update.y_control        is not None: state.y_control        = update.y_control
        if update.loop_recoil      is not None: state.loop_recoil      = update.loop_recoil
        if update.require_aim      is not None: state.require_aim      = update.require_aim
        if update.return_crosshair is not None: state.return_crosshair = update.return_crosshair
        if update.return_speed     is not None: state.return_speed     = update.return_speed
        if update.randomisation    is not None: state.randomisation    = update.randomisation
        if update.rand_strength    is not None: state.rand_strength    = update.rand_strength
        if update.game             is not None: state.game             = update.game
        if update.sensitivity      is not None: state.sensitivity      = update.sensitivity

    return {"ok": True}


@router.post("/enable")
def enable():
    with state.lock:
        state.enabled = True
    return {"enabled": True}


@router.post("/disable")
def disable():
    with state.lock:
        state.enabled = False
    return {"enabled": False}


@router.post("/toggle")
def toggle():
    with state.lock:
        state.enabled = not state.enabled
        enabled = state.enabled
    return {"enabled": enabled}
