import json as _json
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from shared import state, save_async

router = APIRouter(tags=["scripts"])


def _read_script(name: str, game: Optional[str] = None) -> dict:
    """Read a script file (.json preferred, .txt fallback).
    Returns {"content": csv_text, "sensitivity": float, "game": str, "author": str}.
    Raises HTTPException(404) if neither format exists.
    """
    try:
        json_path = state._resolve_path(name, game, ext=".json")
        txt_path = state._resolve_path(name, game, ext=".txt")
    except ValueError:
        raise HTTPException(400, "Invalid path")

    if os.path.exists(json_path):
        with open(json_path) as f:
            data = _json.load(f)
        sensitivity = float(data.get("sensitivity", 1.0))
        steps = data.get("steps", [])
        lines = []
        for item in steps:
            try:
                x, y, d = item[0], item[1], item[2]
                lines.append(f"{x},{y},{int(d)}" if d == int(d) else f"{x},{y},{d}")
            except Exception:
                pass
        return {
            "content": "\n".join(lines),
            "sensitivity": sensitivity,
            "game": data.get("game", ""),
            "author": data.get("author", ""),
        }
    elif os.path.exists(txt_path):
        with open(txt_path) as f:
            return {"content": f.read(), "sensitivity": 1.0, "game": "", "author": ""}
    else:
        raise HTTPException(404, "Script not found")


# ── Scripts ────────────────────────────────────────────────────────────────────

@router.get("/api/scripts/games")
async def list_games():
    return {"games": state.list_games()}


@router.get("/api/scripts")
async def list_scripts(game: Optional[str] = None):
    return {"scripts": state.list_scripts(game), "loaded": state.loaded_script, "games": state.list_games()}


@router.get("/api/scripts/content/{game}/{name}")
async def get_script_content_with_game(game: str, name: str):
    return _read_script(name, game)


@router.get("/api/scripts/content/{name}")
async def get_script_content(name: str):
    # Try flat (no game) first
    try:
        return _read_script(name)
    except HTTPException:
        pass
    # Search game folders
    for game in state.list_games():
        try:
            return _read_script(name, game)
        except HTTPException:
            continue
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
    sensitivity: float = 1.0


@router.post("/api/scripts/save")
async def save_script(s: ScriptSave):
    if not state.save_script(s.name, s.content, s.game, s.sensitivity):
        raise HTTPException(500, "Failed to save script")
    full_name = f"{s.game}/{s.name}" if s.game else s.name
    if state.loaded_script in (full_name, s.name):
        state.load_script(s.name, s.game)
    await save_async()
    return {"ok": True}


@router.delete("/api/scripts/{game}/{name}")
async def delete_script_with_game(game: str, name: str):
    if not state.delete_script(name, game):
        raise HTTPException(404, "Script not found")
    await save_async()
    return {"ok": True}


@router.delete("/api/scripts/{name}")
async def delete_script(name: str):
    if not state.delete_script(name):
        raise HTTPException(404, "Script not found")
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
    return _read_script(weapon, game)


@router.post("/api/patterns/{game}/{weapon}")
async def save_pattern(game: str, weapon: str, request: Request):
    body = await request.body()
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        data = _json.loads(body)
        content = data.get("content", "")
        sensitivity = float(data.get("sensitivity", 1.0))
    else:
        content = body.decode()
        sensitivity = 1.0
    if not state.save_script(weapon, content, game, sensitivity):
        raise HTTPException(500, "Failed to save pattern")
    full_name = f"{game}/{weapon}"
    if state.loaded_script in (full_name, weapon):
        state.load_script(weapon, game)
    await save_async()
    return {"saved": True}


@router.delete("/api/patterns/{game}/{weapon}")
async def delete_pattern(game: str, weapon: str):
    if not state.delete_script(weapon, game):
        raise HTTPException(404, "Pattern not found")
    await save_async()
    return {"deleted": True}
