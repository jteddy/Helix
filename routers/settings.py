from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from shared import state, save_async

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    game_scalar:      Optional[str]   = None
    game_sensitivity: Optional[float] = None
    theme:            Optional[str]   = None


@router.post("")
async def update_settings(u: SettingsUpdate):
    with state._lock:
        if u.game_scalar      is not None: state.game_scalar      = u.game_scalar
        if u.game_sensitivity is not None: state.game_sensitivity = u.game_sensitivity
        if u.theme            is not None: state.theme            = u.theme
    await save_async()
    return {"ok": True}
