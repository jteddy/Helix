from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from shared import state, save_async

router = APIRouter(prefix="/api/flashlight", tags=["flashlight"])


class FlashlightUpdate(BaseModel):
    enabled:           Optional[bool]  = None
    keybind:           Optional[str]   = None
    hold_threshold_ms: Optional[float] = None
    cooldown_ms:       Optional[float] = None
    pre_fire_min_ms:   Optional[float] = None
    pre_fire_max_ms:   Optional[float] = None


@router.post("/toggle")
async def toggle_flashlight():
    state.toggle_flashlight()
    await save_async()
    return {"enabled": state.flashlight_enabled}


@router.post("")
async def update_flashlight(u: FlashlightUpdate):
    with state._lock:
        if u.enabled           is not None: state.flashlight_enabled = u.enabled
        if u.keybind           is not None: state.flashlight_keybind = u.keybind
        if u.hold_threshold_ms is not None: state.hold_threshold_ms  = u.hold_threshold_ms
        if u.cooldown_ms       is not None: state.cooldown_ms        = u.cooldown_ms
        if u.pre_fire_min_ms   is not None: state.pre_fire_min_ms    = u.pre_fire_min_ms
        if u.pre_fire_max_ms   is not None: state.pre_fire_max_ms    = u.pre_fire_max_ms
    await save_async()
    return {"ok": True}
