from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from shared import state, save_async
from features.cs2.weapon_data import CS2_WEAPONS, CS2_WEAPON_LABELS

router = APIRouter(prefix="/api/cs2", tags=["cs2"])


@router.get("/weapons")
async def list_weapons():
    """Return available built-in CS2 weapon patterns."""
    weapons = [{"key": k, "label": CS2_WEAPON_LABELS[k], "steps": len(v)}
               for k, v in CS2_WEAPONS.items()]
    return {"weapons": weapons, "selected": state.get_cs2_weapon()}


class WeaponSelect(BaseModel):
    weapon: str  # key from CS2_WEAPONS, or "none" to disable


@router.post("/weapon")
async def select_weapon(body: WeaponSelect):
    try:
        state.set_cs2_weapon(body.weapon)
    except ValueError as e:
        raise HTTPException(400, str(e))
    await save_async()
    return {"ok": True, "weapon": state.get_cs2_weapon()}
