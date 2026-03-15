"""
api/patterns.py
---------------
Vector (pattern) CRUD endpoints.
Patterns are stored as plain .txt files: x,y,ms per line.
Loading a pattern also pushes the vectors into the recoil loop state.
"""

import os
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
from core.state import state

router = APIRouter(prefix="/api/patterns", tags=["patterns"])

PATTERNS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "patterns")
os.makedirs(PATTERNS_DIR, exist_ok=True)


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("")
def list_patterns():
    """Return all patterns grouped by game."""
    result = {}
    for game in sorted(os.listdir(PATTERNS_DIR)):
        gp = os.path.join(PATTERNS_DIR, game)
        if not os.path.isdir(gp):
            continue
        weapons = [f[:-4] for f in sorted(os.listdir(gp)) if f.endswith(".txt")]
        if weapons:
            result[game] = weapons
    return result


# ── Load ──────────────────────────────────────────────────────────────────────

@router.get("/{game}/{weapon}")
def get_pattern(game: str, weapon: str):
    """Return raw vector text for a pattern."""
    path = os.path.join(PATTERNS_DIR, game, f"{weapon}.txt")
    if not os.path.exists(path):
        raise HTTPException(404, "Pattern not found")
    with open(path) as f:
        return PlainTextResponse(f.read())


@router.post("/{game}/{weapon}/activate")
def activate_pattern(game: str, weapon: str):
    """
    Load a pattern into the recoil loop immediately.
    This is what the control panel calls when the user selects a weapon.
    """
    path = os.path.join(PATTERNS_DIR, game, f"{weapon}.txt")
    if not os.path.exists(path):
        raise HTTPException(404, "Pattern not found")
    with open(path) as f:
        text = f.read()
    count = state.load_vectors_from_txt(text)
    with state.lock:
        state.active_game   = game
        state.active_weapon = weapon
    return {"ok": True, "shots": count, "game": game, "weapon": weapon}


# ── Save ──────────────────────────────────────────────────────────────────────

@router.post("/{game}/{weapon}")
async def save_pattern(game: str, weapon: str, request: Request):
    """Save a pattern. Body is raw x,y,ms lines."""
    body = await request.body()
    folder = os.path.join(PATTERNS_DIR, game)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{weapon}.txt")
    with open(path, "w") as f:
        f.write(body.decode())
    return {"saved": True, "path": f"{game}/{weapon}"}


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/{game}/{weapon}")
def delete_pattern(game: str, weapon: str):
    """Delete a pattern."""
    path = os.path.join(PATTERNS_DIR, game, f"{weapon}.txt")
    if not os.path.exists(path):
        raise HTTPException(404, "Pattern not found")
    os.remove(path)
    gp = os.path.join(PATTERNS_DIR, game)
    if not os.listdir(gp):
        os.rmdir(gp)
    return {"deleted": True}
