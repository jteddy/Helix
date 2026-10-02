import os
import platform
import subprocess
import sys
import time
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import shared
from features.recoil.recoil import recoil
from features.recorder.recorder import recorder
from shared import makcu_controller, state

router = APIRouter(tags=["diagnostics"])

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_commit = None


def _git_commit():
    global _commit
    if _commit is None:
        try:
            _commit = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"], cwd=_BASE_DIR,
                capture_output=True, text=True, timeout=2,
            ).stdout.strip() or "unknown"
        except Exception:
            _commit = "unknown"
    return _commit


@router.get("/api/buttons")
def buttons(probe: int = 0):
    out = makcu_controller.button_summary()
    out["stream_enabled"] = None
    out["probe"] = None
    out["probe_note"] = None
    if probe:
        out["stream_enabled"], out["probe"], out["probe_note"] = makcu_controller.probe_buttons()
    return out


class EnableRequest(BaseModel):
    mode: str = "text"


@router.post("/api/buttons/enable")
def buttons_enable(req: EnableRequest):
    if req.mode not in ("text", "binary"):
        raise HTTPException(400, "mode must be 'text' or 'binary'")
    if not makcu_controller.is_connected():
        raise HTTPException(503, "MAKCU is not connected")
    ok, sent = makcu_controller.enable_stream(req.mode)
    return {"ok": ok, "sent": sent}


@router.post("/api/buttons/reset")
def buttons_reset():
    makcu_controller.reset_button_stats()
    return {"ok": True}


class TestMove(BaseModel):
    dx: int = 0
    dy: int = 0


@router.post("/api/device/test-move")
def test_move(req: TestMove):
    if abs(req.dx) > 300 or abs(req.dy) > 300:
        raise HTTPException(400, "dx and dy must be within ±300")
    if not makcu_controller.is_connected():
        raise HTTPException(503, "MAKCU is not connected")
    return {"ok": bool(makcu_controller.simple_move_mouse(req.dx, req.dy))}


@router.get("/api/diagnostics")
def diagnostics():
    """Everything needed to diagnose 'recoil does nothing' in one paste."""
    cfg = state.to_dict()
    cfg["recoil"].pop("scripts_dir", None)          # absolute path: keep it out of pasted reports
    vectors = state.get_active_vectors()
    xs = [v[0] for v in vectors]
    script = {
        "loaded": cfg["recoil"]["loaded_script"],
        "cs2_weapon_override": cfg["settings"]["cs2_weapon"],
        "steps": len(vectors),
        "first_steps": [[v[0], v[1], round(v[2] * 1000)] for v in vectors[:3]],
        "last_steps": [[v[0], v[1], round(v[2] * 1000)] for v in vectors[-3:]],
        "largest_abs_x": max((abs(x) for x in xs), default=0),
        "index_of_largest_abs_x": max(range(len(xs)), key=lambda i: abs(xs[i])) if xs else None,
        "total_duration_ms": round(sum(v[2] for v in vectors) * 1000),
    }
    scalar = recoil.sens_scalar(state)
    now = time.time()
    return {
        "commit": _git_commit(),
        "uptime_s": round(now - shared.started_at),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "recoil_settings": cfg["recoil"],
        "effective_scalar": scalar,
        "settings": cfg["settings"],
        "flashlight": cfg["flashlight"],
        "script": script,
        "buttons": makcu_controller.button_summary(),
        "device": makcu_controller.device_summary(),
        "device_route": makcu_controller.device_route() if not makcu_controller._recording.is_set() else "skipped (recorder running)",
        "recorder": recorder.status(),
        "flags": {
            "spray_active": makcu_controller._spray_active.is_set(),
            "recording": makcu_controller._recording.is_set(),
            "clicking": str(makcu_controller._clicking_button),
            "native_click": makcu_controller._native_click,
        },
    }
