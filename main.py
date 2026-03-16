"""
Cearum Web — FastAPI backend
Runs on the Raspberry Pi, serves the browser UI, holds the MAKCU connection,
and runs the recoil + flashlight loops in background threads.
"""
import asyncio
import json
import os
import threading
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from state import AppState
from mouse.makcu import makcu_controller
from features.recoil.recoil import recoil as recoil_feature
from features.flashlight.flashlight import flashlight as flashlight_feature
import config_manager

# ── App & shared state ────────────────────────────────────────────────────────
app   = FastAPI(title="Cearum Web")
state = AppState()
ws_clients: List[WebSocket] = []

PATTERNS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "patterns")
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))

# ── Static / root ─────────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

@app.get("/")
async def root():
    return FileResponse(os.path.join(BASE_DIR, "static", "index.html"))

# ── WebSocket — live status stream ────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    ws_clients.append(ws)
    try:
        while True:
            await ws.receive_text()          # keep-alive (client sends pings)
    except WebSocketDisconnect:
        if ws in ws_clients:
            ws_clients.remove(ws)

# ── REST: full state snapshot ─────────────────────────────────────────────────
@app.get("/api/state")
async def get_state():
    d = state.to_dict()
    d["makcu_connected"] = makcu_controller.is_connected()
    d["scripts"]         = state.list_scripts()
    d["patterns"]        = _list_patterns()
    return d

# ── REST: Recoil ──────────────────────────────────────────────────────────────
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
    scripts_dir:            Optional[str]   = None

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
    if u.scripts_dir             is not None and os.path.isdir(u.scripts_dir):
        state.scripts_dir = u.scripts_dir
    config_manager.save(state)
    return {"ok": True}

@app.post("/api/recoil/toggle")
async def toggle_recoil():
    state.toggle_recoil()
    config_manager.save(state)
    return {"enabled": state.recoil_enabled}

# ── REST: Scripts ─────────────────────────────────────────────────────────────
@app.get("/api/scripts")
async def list_scripts():
    return {"scripts": state.list_scripts(), "loaded": state.loaded_script}

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

@app.post("/api/scripts/save")
async def save_script(s: ScriptSave):
    state.save_script(s.name, s.content)
    return {"ok": True}

@app.delete("/api/scripts/{name}")
async def delete_script(name: str):
    state.delete_script(name)
    if state.loaded_script == name:
        state.loaded_script = "NONE"
        state.vectors = []
    config_manager.save(state)
    return {"ok": True}

# ── REST: Flashlight ──────────────────────────────────────────────────────────
class FlashlightUpdate(BaseModel):
    enabled:          Optional[bool]  = None
    keybind:          Optional[str]   = None
    hold_threshold_ms:Optional[float] = None
    cooldown_ms:      Optional[float] = None
    pre_fire_min_ms:  Optional[float] = None
    pre_fire_max_ms:  Optional[float] = None

@app.post("/api/flashlight/toggle")
async def toggle_flashlight():
    state.flashlight_enabled = not state.flashlight_enabled
    config_manager.save(state)
    return {"enabled": state.flashlight_enabled}

@app.post("/api/flashlight")
async def update_flashlight(u: FlashlightUpdate):
    if u.enabled           is not None: state.flashlight_enabled  = u.enabled
    if u.keybind           is not None: state.flashlight_keybind  = u.keybind
    if u.hold_threshold_ms is not None: state.hold_threshold_ms   = u.hold_threshold_ms
    if u.cooldown_ms       is not None: state.cooldown_ms         = u.cooldown_ms
    if u.pre_fire_min_ms   is not None: state.pre_fire_min_ms     = u.pre_fire_min_ms
    if u.pre_fire_max_ms   is not None: state.pre_fire_max_ms     = u.pre_fire_max_ms
    config_manager.save(state)
    return {"ok": True}

# ── REST: Settings ────────────────────────────────────────────────────────────
class SettingsUpdate(BaseModel):
    game_scalar:      Optional[str]   = None
    game_sensitivity: Optional[float] = None

@app.post("/api/settings")
async def update_settings(u: SettingsUpdate):
    if u.game_scalar      is not None: state.game_scalar      = u.game_scalar
    if u.game_sensitivity is not None: state.game_sensitivity = u.game_sensitivity
    config_manager.save(state)
    return {"ok": True}

# ── REST: Stream Deck ─────────────────────────────────────────────────────────
@app.get("/api/streamdeck")
async def streamdeck_state():
    """Lightweight polling endpoint for Stream Deck buttons."""
    return {
        "recoil":     state.recoil_enabled,
        "flashlight": state.flashlight_enabled and state.recoil_enabled,
        "makcu":      makcu_controller.is_connected(),
        "script":     state.loaded_script,
    }

# ── REST: Patterns (Vector Editor) ────────────────────────────────────────────
def _list_patterns() -> dict:
    result = {}
    if not os.path.isdir(PATTERNS_DIR):
        return result
    for game in sorted(os.listdir(PATTERNS_DIR)):
        gp = os.path.join(PATTERNS_DIR, game)
        if not os.path.isdir(gp):
            continue
        weapons = sorted(f[:-4] for f in os.listdir(gp) if f.endswith(".txt"))
        if weapons:
            result[game] = weapons
    return result

@app.get("/api/patterns")
async def get_patterns():
    return _list_patterns()

@app.get("/api/patterns/{game}/{weapon}")
async def get_pattern(game: str, weapon: str):
    path = os.path.join(PATTERNS_DIR, game, f"{weapon}.txt")
    if not os.path.exists(path):
        raise HTTPException(404, "Pattern not found")
    with open(path) as f:
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(f.read())

@app.post("/api/patterns/{game}/{weapon}")
async def save_pattern(game: str, weapon: str, request: Request):
    body = await request.body()
    folder = os.path.join(PATTERNS_DIR, game)
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, f"{weapon}.txt"), "w") as f:
        f.write(body.decode())
    return {"saved": True}

@app.delete("/api/patterns/{game}/{weapon}")
async def delete_pattern(game: str, weapon: str):
    path = os.path.join(PATTERNS_DIR, game, f"{weapon}.txt")
    if not os.path.exists(path):
        raise HTTPException(404, "Pattern not found")
    os.remove(path)
    gp = os.path.join(PATTERNS_DIR, game)
    try:
        if not os.listdir(gp):
            os.rmdir(gp)
    except Exception:
        pass
    return {"deleted": True}

# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    os.makedirs(PATTERNS_DIR, exist_ok=True)
    os.makedirs(state.scripts_dir, exist_ok=True)

    config_manager.load(state)

    def _connect():
        if makcu_controller.connect() is None:
            print("[MAKCU] Failed to connect — check USB connection")
        else:
            print("[MAKCU] Connected")

    threading.Thread(target=_connect,                                    daemon=True).start()
    threading.Thread(target=recoil_feature.run_recoil,    args=(state,), daemon=True).start()
    threading.Thread(target=flashlight_feature.run_flashlight, args=(state,), daemon=True).start()

    asyncio.create_task(_broadcast_loop())
    asyncio.create_task(_autosave_loop())

async def _broadcast_loop():
    """Push live status to all connected browsers every 200 ms."""
    while True:
        if ws_clients:
            msg = json.dumps({
                "makcu_connected":  makcu_controller.is_connected(),
                "recoil_enabled":   state.recoil_enabled,
                "flashlight_active": state.flashlight_enabled and state.recoil_enabled,
                "loaded_script":    state.loaded_script,
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

# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    import socket
    try:
        ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        ip = "localhost"
    print(f"\n{'='*40}")
    print(f"  Cearum Web")
    print(f"  http://localhost:8000")
    print(f"  http://{ip}:8000  (network)")
    print(f"{'='*40}\n")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
