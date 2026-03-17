"""
Cearum Web — FastAPI backend
Unified directory: saved_scripts/<game>/<weapon>.txt is used for BOTH
the recoil scripts tab and the vector editor. Flat files in saved_scripts/
root are also supported for backward compatibility.
"""
import asyncio
import hashlib
import json
import os
import threading
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from state import AppState
from mouse.makcu import makcu_controller
from features.recoil.recoil import recoil as recoil_feature
from features.flashlight.flashlight import flashlight as flashlight_feature
from features.recorder.recorder import recorder as recorder_feature
import config_manager

state = AppState()
ws_clients: set[WebSocket] = set()   # FIX: set for O(1) add/remove

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Broadcast state-hash cache (only send when state actually changes) ────────
_last_broadcast_hash: str = ""

# ── Recorder state ────────────────────────────────────────────────────────────
_recorder_pending_result: Optional[str] = None
_recorder_was_recoil_enabled: bool = False


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
    # ── Shutdown ──────────────────────────────────────────────────────────────
    # FIX: gracefully disconnect the MAKCU so it isn't left in a bad state
    makcu_controller.disconnect()
    print("[Cearum] Shutdown complete")


app = FastAPI(title="Cearum Web", lifespan=lifespan)

# FIX: CORS middleware so dev/testing from a different origin works cleanly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static / root ─────────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

@app.get("/")
async def root():
    return FileResponse(os.path.join(BASE_DIR, "static", "index.html"))

# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    """Simple liveness + MAKCU check — useful for scripting and Stream Deck polling."""
    return {"status": "ok", "makcu": makcu_controller.is_connected()}

# ── WebSocket ─────────────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    ws_clients.add(ws)   # FIX: set.add instead of list.append
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_clients.discard(ws)   # FIX: discard is safe even if already removed

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
    await _save_async()
    return {"ok": True}

@app.post("/api/recoil/toggle")
async def toggle_recoil():
    state.toggle_recoil()
    await _save_async()
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
    await _save_async()
    return {"ok": True, "loaded": full_name}

@app.post("/api/scripts/load/{name}")
async def load_script(name: str):
    if not state.load_script(name):
        raise HTTPException(404, "Script not found")
    await _save_async()
    return {"ok": True, "loaded": name}

@app.post("/api/scripts/cycle")
async def cycle_script():
    state.cycle_script()
    await _save_async()
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
    await _save_async()
    return {"ok": True}

@app.delete("/api/scripts/{game}/{name}")
async def delete_script_with_game(game: str, name: str):
    state.delete_script(name, game)
    await _save_async()
    return {"ok": True}

@app.delete("/api/scripts/{name}")
async def delete_script(name: str):
    state.delete_script(name)
    await _save_async()
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
    await _save_async()
    return {"enabled": state.flashlight_enabled}

@app.post("/api/flashlight")
async def update_flashlight(u: FlashlightUpdate):
    with state._lock:
        if u.enabled           is not None: state.flashlight_enabled = u.enabled
        if u.keybind           is not None: state.flashlight_keybind = u.keybind
        if u.hold_threshold_ms is not None: state.hold_threshold_ms  = u.hold_threshold_ms
        if u.cooldown_ms       is not None: state.cooldown_ms        = u.cooldown_ms
        if u.pre_fire_min_ms   is not None: state.pre_fire_min_ms    = u.pre_fire_min_ms
        if u.pre_fire_max_ms   is not None: state.pre_fire_max_ms    = u.pre_fire_max_ms
    await _save_async()
    return {"ok": True}

# ── Settings ──────────────────────────────────────────────────────────────────
class SettingsUpdate(BaseModel):
    game_scalar:      Optional[str]   = None
    game_sensitivity: Optional[float] = None

@app.post("/api/settings")
async def update_settings(u: SettingsUpdate):
    with state._lock:
        if u.game_scalar      is not None: state.game_scalar      = u.game_scalar
        if u.game_sensitivity is not None: state.game_sensitivity = u.game_sensitivity
    await _save_async()
    return {"ok": True}

# ── Vector Editor — patterns API (same dir as scripts) ────────────────────────
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
    full_name = f"{game}/{weapon}"
    if state.loaded_script in (full_name, weapon):
        state.load_script(weapon, game)
    await _save_async()   # FIX 7: persist config so loaded_script survives restart
    return {"saved": True}

@app.delete("/api/patterns/{game}/{weapon}")
async def delete_pattern(game: str, weapon: str):
    state.delete_script(weapon, game)
    await _save_async()   # FIX: was missing — state must be persisted after delete
    return {"deleted": True}

# ── Recorder ──────────────────────────────────────────────────────────────────
class RecorderArm(BaseModel):
    bucket_ms: Optional[int] = 85

@app.post("/api/recorder/arm")
async def recorder_arm(u: RecorderArm):
    global _recorder_pending_result, _recorder_was_recoil_enabled
    _recorder_pending_result = None
    _recorder_was_recoil_enabled = state.recoil_enabled
    state.recoil_enabled = False

    def _on_result(buckets):
        global _recorder_pending_result
        lines = ["# x_offset, y_offset, delay_ms"]
        lines += [f"{x}, {y}, {ms}" for x, y, ms in buckets]
        _recorder_pending_result = "\n".join(lines)
        state.recoil_enabled = _recorder_was_recoil_enabled
        recorder_feature.disarm()

    ok = recorder_feature.arm(_on_result, u.bucket_ms or 85)
    return {"armed": ok}

@app.post("/api/recorder/disarm")
async def recorder_disarm():
    global _recorder_was_recoil_enabled
    recorder_feature.disarm()
    state.recoil_enabled = _recorder_was_recoil_enabled
    return {"armed": False}

@app.get("/api/recorder/status")
async def recorder_status():
    return {"armed": recorder_feature.is_armed(), "recording": recorder_feature.is_recording()}

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
    """Push status to all WebSocket clients every 200 ms."""
    global _last_broadcast_hash, _recorder_pending_result
    while True:
        if ws_clients:
            # Flush any pending recorder result immediately
            if _recorder_pending_result is not None:
                result_msg = json.dumps({"recorder_result": _recorder_pending_result})
                _recorder_pending_result = None
                dead = set()
                for ws in list(ws_clients):
                    try:
                        await ws.send_text(result_msg)
                    except Exception:
                        dead.add(ws)
                ws_clients.difference_update(dead)

            msg = json.dumps({
                "makcu_connected":    makcu_controller.is_connected(),
                "recoil_enabled":     state.recoil_enabled,
                "flashlight_active":  state.flashlight_enabled and state.recoil_enabled,
                "loaded_script":      state.loaded_script,
                "lmb_pressed":        makcu_controller.get_button_state("LMB"),
                "recorder_armed":     recorder_feature.is_armed(),
                "recorder_recording": recorder_feature.is_recording(),
            })
            h = hashlib.md5(msg.encode()).hexdigest()
            if h != _last_broadcast_hash:
                _last_broadcast_hash = h
                dead = set()
                for ws in list(ws_clients):
                    try:
                        await ws.send_text(msg)
                    except Exception:
                        dead.add(ws)
                ws_clients.difference_update(dead)
        await asyncio.sleep(0.2)

async def _autosave_loop():
    while True:
        await asyncio.sleep(30)
        await _save_async()

async def _save_async():
    """Run config_manager.save in a thread-pool executor so it never
    blocks the async event loop on file I/O."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, config_manager.save, state)

if __name__ == "__main__":
    import uvicorn, socket
    try:
        ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        ip = "localhost"
    print(f"\n{'='*40}\n  Cearum Web\n  http://localhost:8000\n  http://{ip}:8000\n{'='*40}\n")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
