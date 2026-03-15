"""
api/status.py
-------------
WebSocket endpoint that pushes live status to all connected browsers.

Broadcasts every 250ms:
  - MAKCU connection state
  - Recoil enabled/active
  - Active game and weapon

The frontend uses this to update the status pill and control panel
without polling.
"""

import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from core.state import state

router = APIRouter(tags=["status"])

_clients: list[WebSocket] = []


@router.websocket("/ws/status")
async def status_ws(ws: WebSocket):
    await ws.accept()
    _clients.append(ws)
    try:
        while True:
            # Push status every 250ms
            payload = {
                "makcu_connected": state.makcu_connected,
                "enabled":         state.enabled,
                "recoil_active":   state.recoil_active,
                "active_game":     state.active_game,
                "active_weapon":   state.active_weapon,
            }
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                break
            await asyncio.sleep(0.25)
    except WebSocketDisconnect:
        pass
    finally:
        if ws in _clients:
            _clients.remove(ws)
