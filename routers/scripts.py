import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from shared import state, save_async

router = APIRouter(tags=["scripts"])


# ── Scripts ────────────────────────────────────────────────────────────────────

@router.get("/api/scripts/games")
async def list_games():
    return {"games": state.list_games()}


@router.get("/api/scripts")
async def list_scripts(game: Optional[str] = None):
    return {"scripts": state.list_scripts(game), "loaded": state.loaded_script, "games": state.list_games()}


@router.get("/api/scripts/content/{game}/{name}")
async def get_script_content_with_game(game: str, name: str):
    try:
        path = state._resolve_path(name, game)
    except ValueError:
        raise HTTPException(400, "Invalid path")
    if not os.path.exists(path):
        raise HTTPException(404, "Script not found")
    with open(path) as f:
        return PlainTextResponse(f.read())


@router.get("/api/scripts/content/{name}")
async def get_script_content(name: str):
    try:
        flat = state._resolve_path(name)
    except ValueError:
        raise HTTPException(400, "Invalid path")
    if os.path.exists(flat):
        with open(flat) as f:
            return PlainTextResponse(f.read())
    for game in state.list_games():
        try:
            path = state._resolve_path(name, game)
        except ValueError:
            continue
        if os.path.exists(path):
            with open(path) as f:
                return PlainTextResponse(f.read())
    raise HTTPException(404, "Script not found")


@router.post("/api/scripts/load/{game}/{name}")
async def load_script_with_game(game: str, name: str):
    full_name = f"{game}/{name}"
    if not state.load_script(name, game):
        raise HTTPException(404, "Script not found")
    await save_async()
    return {"ok": True, "loaded": full_name}


@router.post("/api/scripts/load/{name}")
async def load_script(name: str):
    if not state.load_script(name):
        raise HTTPException(404, "Script not found")
    await save_async()
    return {"ok": True, "loaded": name}


@router.post("/api/scripts/cycle")
async def cycle_script():
    state.cycle_script()
    await save_async()
    return {"loaded": state.loaded_script}


class ScriptSave(BaseModel):
    name: str
    content: str
    game: Optional[str] = None


@router.post("/api/scripts/save")
async def save_script(s: ScriptSave):
    state.save_script(s.name, s.content, s.game)
    full_name = f"{s.game}/{s.name}" if s.game else s.name
    if state.loaded_script in (full_name, s.name):
        state.load_script(s.name, s.game)
    await save_async()
    return {"ok": True}


@router.delete("/api/scripts/{game}/{name}")
async def delete_script_with_game(game: str, name: str):
    state.delete_script(name, game)
    await save_async()
    return {"ok": True}


@router.delete("/api/scripts/{name}")
async def delete_script(name: str):
    state.delete_script(name)
    await save_async()
    return {"ok": True}


# ── Patterns (same storage, separate prefix) ───────────────────────────────────

@router.get("/api/patterns")
async def get_patterns():
    result = {}
    for game in state.list_games():
        weapons = state.list_scripts(game)
        if weapons:
            result[game] = weapons
    return result


@router.get("/api/patterns/{game}/{weapon}")
async def get_pattern(game: str, weapon: str):
    try:
        path = state._resolve_path(weapon, game)
    except ValueError:
        raise HTTPException(400, "Invalid path")
    if not os.path.exists(path):
        raise HTTPException(404, "Pattern not found")
    with open(path) as f:
        return PlainTextResponse(f.read())


@router.post("/api/patterns/{game}/{weapon}")
async def save_pattern(game: str, weapon: str, request: Request):
    body = await request.body()
    content = body.decode()
    state.save_script(weapon, content, game)
    full_name = f"{game}/{weapon}"
    if state.loaded_script in (full_name, weapon):
        state.load_script(weapon, game)
    await save_async()
    return {"saved": True}


@router.delete("/api/patterns/{game}/{weapon}")
async def delete_pattern(game: str, weapon: str):
    state.delete_script(weapon, game)
    await save_async()
    return {"deleted": True}
