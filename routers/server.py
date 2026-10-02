import asyncio
import os
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request

import shared
from shared import save_async

router = APIRouter(prefix="/api/server", tags=["server"])


def restart_mode():
    """'systemd' (the supervisor relaunches us), 'exec' (we re-exec ourselves),
    or None when a restart is not possible from here."""
    if shared.server is None or os.name == "nt":
        return None
    return "systemd" if os.environ.get("INVOCATION_ID") else "exec"


@router.get("")
async def server_info():
    mode = restart_mode()
    return {
        "restart_supported": mode is not None,
        "mode": mode,
        "started_at": shared.started_at,
        "pid": os.getpid(),
    }


@router.post("/restart")
async def restart_server(request: Request):
    # CORS is wide open and there is no auth, so a page on another site could
    # otherwise restart the server through a visitor's browser. Browsers always
    # send Origin on cross-origin POSTs; curl and the Stream Deck do not.
    origin = request.headers.get("origin")
    if origin and urlparse(origin).netloc != request.headers.get("host"):
        raise HTTPException(403, "Cross-origin restart blocked")

    mode = restart_mode()
    if mode is None:
        raise HTTPException(
            501,
            "Restart is only available when Helix is started with `python main.py` on Linux",
        )

    await save_async()
    who = request.client.host if request.client else "unknown"
    print(f"[Helix] Restart requested by {who} ({mode})")
    shared.restart_requested = True
    # Let this response reach the browser before the server starts shutting down.
    asyncio.get_running_loop().call_later(0.3, _begin_shutdown)
    return {"ok": True, "mode": mode}


def _begin_shutdown():
    shared.server.should_exit = True
