from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from shared import state, save_async

router = APIRouter(prefix="/api/recoil", tags=["recoil"])


class RecoilUpdate(BaseModel):
    enabled:                Optional[bool]  = None
    toggle_keybind:         Optional[str]   = None
    cycle_keybind:          Optional[str]   = None
    require_aim:            Optional[bool]  = None
    loop_recoil:            Optional[bool]  = None
    randomisation:          Optional[bool]  = None
    return_crosshair:       Optional[bool]  = None
    randomisation_strength: Optional[float] = None
    recoil_scalar:          Optional[float] = None
    x_control:              Optional[float] = None
    y_control:              Optional[float] = None
    return_speed:           Optional[float] = None


@router.post("")
async def update_recoil(u: RecoilUpdate):
    with state._lock:
        if u.enabled                 is not None: state.recoil_enabled         = u.enabled
        if u.toggle_keybind          is not None: state.toggle_keybind         = u.toggle_keybind
        if u.cycle_keybind           is not None: state.cycle_keybind          = u.cycle_keybind
        if u.require_aim             is not None: state.require_aim            = u.require_aim
        if u.loop_recoil             is not None: state.loop_recoil            = u.loop_recoil
        if u.randomisation           is not None: state.randomisation          = u.randomisation
        if u.return_crosshair        is not None: state.return_crosshair       = u.return_crosshair
        if u.randomisation_strength  is not None: state.randomisation_strength = u.randomisation_strength
        if u.recoil_scalar           is not None: state.recoil_scalar          = u.recoil_scalar
        if u.x_control               is not None: state.x_control              = u.x_control
        if u.y_control               is not None: state.y_control              = u.y_control
        if u.return_speed            is not None: state.return_speed           = u.return_speed
    await save_async()
    return {"ok": True}


@router.post("/toggle")
async def toggle_recoil():
    state.toggle_recoil()
    await save_async()
    return {"enabled": state.recoil_enabled}
