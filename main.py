"""
Cearum Web — FastAPI backend
Unified directory: saved_scripts/<game>/<weapon>.txt is used for BOTH
the recoil scripts tab and the vector editor. Flat files in saved_scripts/
root are also supported for backward compatibility.
"""
import asyncio
import json
import os
import threading
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from state import AppState
from mouse.makcu import makcu_controller
from features.recoil.recoil import recoil as recoil_feature
from features.flashlight.flashlight import flashlight as flashlight_feature
import config_manager

state = AppState()
ws_clients: List[WebSocket] = []

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ── Lifespan (replaces deprecated @app.on_event) ──────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    os.makedirs(state.scripts_dir, exist_ok=True)
    config_manager.load(state)

    def _connect():
        if makcu_controller.connect() is None:
            print("[MAKCU] Failed to connect — check USB connection")
        else:
            print("[MAKCU] Connected")

    threading.Thread(target=_connect,                                             daemon=True).start()
    threading.Thread(target=recoil_feature.run_recoil,    args=(state,),         daemon=True).start()
    threading.Thread(target=flashlight_feature.run_flashlight, args=(state,),    daemon=True).start()

    asyncio.create_task(_broadcast_loop())
    asyncio.create_task(_autosave_loop())

    yield
    # ── Shutdown (add cleanup here if needed) ─────────────────────────────────


app = FastAPI(title="Cearum Web", lifespan=lifespan)

# ── Static / root ─────────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

@app.get("/")
async def root():
    return FileResponse(os.path.join(BASE_DIR, "static", "index.html"))

# ── WebSocket ─────────────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    ws_clients.append(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        if ws in ws_clients:
            ws_clients.remove(ws)

# ── Full state snapshot ───────────────────────────────────────────────────────
@app.get("/api/state")
async def get_state():
    d = state.to_dict()
    d["makcu_connected"] = makcu_controller.is_connected()
    d["scripts"]         = state.list_scripts()
    d["games"]           = state.list_games()
    return d

# ── Recoil ────────────────────────────────────────────────────────────────────
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

@app.post("/api/recoil")
async def update_recoil(u: RecoilUpdate):
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
    config_manager.save(state)
    return {"ok": True}

@app.post("/api/recoil/toggle")
async def toggle_recoil():
    state.toggle_recoil()
    config_manager.save(state)
    return {"enabled": state.recoil_enabled}

# ── Scripts (unified with vector editor) ──────────────────────────────────────
@app.get("/api/scripts/games")
async def list_games():
    """List game subfolders inside scripts_dir."""
    return {"games": state.list_games()}

@app.get("/api/scripts")
async def list_scripts(game: Optional[str] = None):
    """
    List scripts. If game is provided, list scripts in that subfolder.
    Otherwise return flat scripts in the root scripts_dir.
    """
    return {"scripts": state.list_scripts(game), "loaded": state.loaded_script, "games": state.list_games()}

@app.get("/api/scripts/content/{game}/{name}")
async def get_script_content_with_game(game: str, name: str):
    path = os.path.join(state.scripts_dir, game, f"{name}.txt")
    if not os.path.exists(path):
        raise HTTPException(404, "Script not found")
    with open(path) as f:
        return PlainTextResponse(f.read())

@app.get("/api/scripts/content/{name}")
async def get_script_content(name: str):
    # Try flat first, then search game subfolders
    flat = os.path.join(state.scripts_dir, f"{name}.txt")
    if os.path.exists(flat):
        with open(flat) as f:
            return PlainTextResponse(f.read())
    # Search in game subfolders
    for game in state.list_games():
        path = os.path.join(state.scripts_dir, game, f"{name}.txt")
        if os.path.exists(path):
            with open(path) as f:
                return PlainTextResponse(f.read())
    raise HTTPException(404, "Script not found")

@app.post("/api/scripts/load/{game}/{name}")
async def load_script_with_game(game: str, name: str):
    full_name = f"{game}/{name}"
    if not state.load_script(name, game):
        raise HTTPException(404, "Script not found")
    config_manager.save(state)
    return {"ok": True, "loaded": full_name}

@app.post("/api/scripts/load/{name}")
async def load_script(name: str):
    if not state.load_script(name):
        raise HTTPException(404, "Script not found")
    config_manager.save(state)
    return {"ok": True, "loaded": name}

@app.post("/api/scripts/cycle")
async def cycle_script():
    state.cycle_script()
    config_manager.save(state)
    return {"loaded": state.loaded_script}

class ScriptSave(BaseModel):
    name: str
    content: str
    game: Optional[str] = None   # if provided, saves to saved_scripts/<game>/<n>.txt

@app.post("/api/scripts/save")
async def save_script(s: ScriptSave):
    state.save_script(s.name, s.content, s.game)
    # If this file is currently loaded, refresh in-memory vectors via lock-safe load_script
    full_name = f"{s.game}/{s.name}" if s.game else s.name
    if state.loaded_script in (full_name, s.name):
        state.load_script(s.name, s.game)
    # persist state after updating vectors
    config_manager.save(state)
    return {"ok": True}

@app.delete("/api/scripts/{game}/{name}")
async def delete_script_with_game(game: str, name: str):
    state.delete_script(name, game)
    config_manager.save(state)
    return {"ok": True}

@app.delete("/api/scripts/{name}")
async def delete_script(name: str):
    state.delete_script(name)
    config_manager.save(state)
    return {"ok": True}

# ── Flashlight ────────────────────────────────────────────────────────────────
class FlashlightUpdate(BaseModel):
    enabled:           Optional[bool]  = None
    keybind:           Optional[str]   = None
    hold_threshold_ms: Optional[float] = None
    cooldown_ms:       Optional[float] = None
    pre_fire_min_ms:   Optional[float] = None
    pre_fire_max_ms:   Optional[float] = None

@app.post("/api/flashlight/toggle")
async def toggle_flashlight():
    state.toggle_flashlight()
    config_manager.save(state)
    return {"enabled": state.flashlight_enabled}

@app.post("/api/flashlight")
async def update_flashlight(u: FlashlightUpdate):
    if u.enabled           is not None: state.flashlight_enabled = u.enabled
    if u.keybind           is not None: state.flashlight_keybind = u.keybind
    if u.hold_threshold_ms is not None: state.hold_threshold_ms  = u.hold_threshold_ms
    if u.cooldown_ms       is not None: state.cooldown_ms        = u.cooldown_ms
    if u.pre_fire_min_ms   is not None: state.pre_fire_min_ms    = u.pre_fire_min_ms
    if u.pre_fire_max_ms   is not None: state.pre_fire_max_ms    = u.pre_fire_max_ms
    config_manager.save(state)
    return {"ok": True}

# ── Settings ──────────────────────────────────────────────────────────────────
class SettingsUpdate(BaseModel):
    game_scalar:      Optional[str]   = None
    game_sensitivity: Optional[float] = None

@app.post("/api/settings")
async def update_settings(u: SettingsUpdate):
    if u.game_scalar      is not None: state.game_scalar      = u.game_scalar
    if u.game_sensitivity is not None: state.game_sensitivity = u.game_sensitivity
    config_manager.save(state)
    return {"ok": True}

# ── Vector Editor — patterns API (now same dir as scripts) ────────────────────
# patterns/<game>/<weapon>.txt → saved_scripts/<game>/<weapon>.txt

@app.get("/api/patterns")
async def get_patterns():
    """Return all game/weapon groups from saved_scripts subfolders."""
    result = {}
    for game in state.list_games():
        weapons = state.list_scripts(game)
        if weapons:
            result[game] = weapons
    return result

@app.get("/api/patterns/{game}/{weapon}")
async def get_pattern(game: str, weapon: str):
    path = os.path.join(state.scripts_dir, game, f"{weapon}.txt")
    if not os.path.exists(path):
        raise HTTPException(404, "Pattern not found")
    with open(path) as f:
        return PlainTextResponse(f.read())

@app.post("/api/patterns/{game}/{weapon}")
async def save_pattern(game: str, weapon: str, request: Request):
    body = await request.body()
    content = body.decode()
    state.save_script(weapon, content, game)
    # If this pattern is the currently loaded script, refresh vectors via lock-safe load_script
    full_name = f"{game}/{weapon}"
    if state.loaded_script in (full_name, weapon):
        state.load_script(weapon, game)
    return {"saved": True}

@app.delete("/api/patterns/{game}/{weapon}")
async def delete_pattern(game: str, weapon: str):
    state.delete_script(weapon, game)
    return {"deleted": True}

# ── Stream Deck ───────────────────────────────────────────────────────────────
@app.get("/api/streamdeck")
async def streamdeck_state():
    return {
        "recoil":     state.recoil_enabled,
        "flashlight": state.flashlight_enabled and state.recoil_enabled,
        "makcu":      makcu_controller.is_connected(),
        "script":     state.loaded_script,
    }

# ── Background tasks ──────────────────────────────────────────────────────────
async def _broadcast_loop():
    while True:
        if ws_clients:
            msg = json.dumps({
                "makcu_connected":   makcu_controller.is_connected(),
                "recoil_enabled":    state.recoil_enabled,
                "flashlight_active": state.flashlight_enabled and state.recoil_enabled,
                "loaded_script":     state.loaded_script,
            })
            dead = []
            for ws in list(ws_clients):
                try:
                    await ws.send_text(msg)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                if ws in ws_clients:
                    ws_clients.remove(ws)
        await asyncio.sleep(0.2)

async def _autosave_loop():
    while True:
        await asyncio.sleep(30)
        config_manager.save(state)

if __name__ == "__main__":
    import uvicorn, socket
    try:
        ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        ip = "localhost"
    print(f"\n{'='*40}\n  Cearum Web\n  http://localhost:8000\n  http://{ip}:8000\n{'='*40}\n")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
