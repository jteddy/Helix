from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from mouse.keys import normalize_key
from shared import state, save_async

router = APIRouter(prefix="/api/hold_breath", tags=["hold_breath"])

TRIGGERS = ("RMB", "MMB", "M4", "M5")   # LMB fires, so it cannot be the aim button
MODES = ("hold", "toggle")
MAX_DELAY_MS = 2000
MAX_HOLD_MS = 30000


class HoldBreathUpdate(BaseModel):
    enabled:        Optional[bool]  = None
    trigger:        Optional[str]   = None
    ads_mode:       Optional[str]   = None
    breath_mode:    Optional[str]   = None
    key:            Optional[str]   = None   # key name from mouse/keys.py, or NONE
    tap_on_release: Optional[bool]  = None
    delay_ms:       Optional[float] = None
    max_hold_ms:    Optional[float] = None


def _mode(value, field):
    if value is None:
        return None
    v = value.strip().lower()
    if v not in MODES:
        raise HTTPException(400, f"{field} must be hold or toggle")
    return v


@router.post("/toggle")
async def toggle_hold_breath():
    state.toggle_hold_breath()
    await save_async()
    return {"enabled": state.get_hold_breath()["enabled"]}


@router.post("")
async def update_hold_breath(u: HoldBreathUpdate):
    # Validate everything first, so a bad field never leaves a half-applied update.
    trigger = None
    if u.trigger is not None:
        trigger = u.trigger.strip().upper()
        if trigger not in TRIGGERS:
            raise HTTPException(400, f"trigger must be one of {', '.join(TRIGGERS)}")
    ads = _mode(u.ads_mode, "ads_mode")
    breath = _mode(u.breath_mode, "breath_mode")
    key = None
    if u.key is not None:
        key = "NONE" if u.key.strip().upper() in ("", "NONE") else normalize_key(u.key)
        if key is None:
            raise HTTPException(400, f"Unknown key: {u.key}")
    if u.delay_ms is not None and not 0 <= u.delay_ms <= MAX_DELAY_MS:
        raise HTTPException(400, f"delay_ms must be 0-{MAX_DELAY_MS}")
    if u.max_hold_ms is not None and not 0 <= u.max_hold_ms <= MAX_HOLD_MS:
        raise HTTPException(400, f"max_hold_ms must be 0-{MAX_HOLD_MS} (0 = no limit)")

    with state._lock:
        if u.enabled        is not None: state.hb_enabled        = u.enabled
        if trigger          is not None: state.hb_trigger        = trigger
        if ads              is not None: state.hb_ads_mode       = ads
        if breath           is not None: state.hb_breath_mode    = breath
        if key              is not None: state.hb_key            = key
        if u.tap_on_release is not None: state.hb_tap_on_release = u.tap_on_release
        if u.delay_ms       is not None: state.hb_delay_ms       = float(u.delay_ms)
        if u.max_hold_ms    is not None: state.hb_max_hold_ms    = float(u.max_hold_ms)
    await save_async()
    return {"ok": True}
