"""
main.py
-------
Cearum Web — FastAPI entry point.

Startup sequence:
  1. Connect to MAKCU device
  2. Start reconnect watchdog
  3. Start recoil loop thread
  4. Mount API routes
  5. Serve frontend

Run:
    python main.py
    
Then open http://localhost:8000 (Windows) or http://<pi-ip>:8000 (Pi/Linux).
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from core.makcu_device  import device
from core.recoil_loop   import start_recoil_loop
from api.config         import router as config_router
from api.patterns       import router as patterns_router
from api.status         import router as status_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    print("\n================================")
    print(" Cearum Web")
    print(" http://localhost:8000")
    print(" Ctrl+C to stop")
    print("================================\n")

    # Connect to MAKCU — non-fatal if not present at startup
    connected = device.connect()
    if not connected:
        print("[startup] MAKCU not connected — will keep retrying in background.")

    # Background reconnect watchdog (checks every 3 seconds)
    device.reconnect_loop(interval=3.0)

    # Start the recoil loop thread
    start_recoil_loop()

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    device.disconnect()
    print("[shutdown] Done.")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="Cearum Web", lifespan=lifespan)

# Routes
app.include_router(config_router)
app.include_router(patterns_router)
app.include_router(status_router)

# Static frontend
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "frontend", "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
