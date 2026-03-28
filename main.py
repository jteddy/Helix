"""
Helix — FastAPI backend
Unified directory: saved_scripts/<game>/<weapon>.txt is used for BOTH
the recoil scripts tab and the vector editor. Flat files in saved_scripts/
root are also supported for backward compatibility.
"""
import asyncio
import hashlib
import json
import logging
import os
import threading
from contextlib import asynccontextmanager

# Suppress uvicorn access-log noise from high-frequency polling endpoints.
class _SuppressPollingLogs(logging.Filter):
    _MUTED = ("/api/streamdeck", "/api/health")
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not any(ep in msg for ep in self._MUTED)

logging.getLogger("uvicorn.access").addFilter(_SuppressPollingLogs())

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# shared singletons — must be imported before routers so state is initialised once
from shared import state, makcu_controller, save_async
import config_manager
from features.recoil.recoil import recoil as recoil_feature
from features.flashlight.flashlight import flashlight as flashlight_feature, shutdown_executor as _shutdown_flashlight_executor

from routers import recoil, scripts, flashlight, settings, cs2, streamdeck

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ws_clients: set[WebSocket] = set()
_last_broadcast_hash: str = ""


# ── Lifespan ───────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(state.scripts_dir, exist_ok=True)
    config_manager.load(state)

    def _connect():
        if makcu_controller.connect() is None:
            print("[MAKCU] Failed to connect — check USB connection")
        else:
            print("[MAKCU] Connected")

    threading.Thread(target=_connect,                                              daemon=True).start()
    threading.Thread(target=recoil_feature.run_recoil,     args=(state,),         daemon=True).start()
    threading.Thread(target=flashlight_feature.run_flashlight, args=(state,),     daemon=True).start()

    asyncio.create_task(_broadcast_loop())
    asyncio.create_task(_autosave_loop())

    yield

    _shutdown_flashlight_executor()
    makcu_controller.disconnect()
    print("[Helix] Shutdown complete")


app = FastAPI(title="Helix", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static / root ──────────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

@app.get("/")
async def root():
    return FileResponse(os.path.join(BASE_DIR, "static", "index.html"))

# ── Health ─────────────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {"status": "ok", "makcu": makcu_controller.is_connected()}

# ── WebSocket ──────────────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    ws_clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_clients.discard(ws)

# ── Full state snapshot ────────────────────────────────────────────────────────
@app.get("/api/state")
async def get_state():
    d = state.to_dict()
    d["makcu_connected"] = makcu_controller.is_connected()
    d["scripts"]         = state.list_scripts()
    d["games"]           = state.list_games()
    return d

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(recoil.router)
app.include_router(scripts.router)
app.include_router(flashlight.router)
app.include_router(settings.router)
app.include_router(cs2.router)
app.include_router(streamdeck.router)

# ── Background tasks ───────────────────────────────────────────────────────────
async def _broadcast_loop():
    global _last_broadcast_hash
    while True:
        if ws_clients:
            msg = json.dumps({
                "makcu_connected":          makcu_controller.is_connected(),
                "recoil_enabled":           state.recoil_enabled,
                "flashlight_enabled":       state.flashlight_enabled,
                "flashlight_active":        state.flashlight_enabled and state.recoil_enabled,
                "loaded_script":            state.loaded_script,
                "lmb_pressed":              makcu_controller.get_button_state("LMB"),
                "recoil_scalar":            state.recoil_scalar,
                "x_control":                state.x_control,
                "y_control":                state.y_control,
                "randomisation_strength":   state.randomisation_strength,
                "return_speed":             state.return_speed,
                "randomisation":            state.randomisation,
                "return_crosshair":         state.return_crosshair,
                "require_aim":              state.require_aim,
                "loop_recoil":              state.loop_recoil,
                "toggle_keybind":           state.toggle_keybind,
                "cycle_keybind":            state.cycle_keybind,
                "theme":                    state.theme,
                "burst_history":            state.get_burst_history(),
                "cs2_weapon":               state.cs2_weapon,
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
        await save_async()


if __name__ == "__main__":
    import uvicorn, socket
    try:
        ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        ip = "localhost"
    print(f"\n{'='*40}\n  Helix\n  http://localhost:8000\n  http://{ip}:8000\n{'='*40}\n")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
