from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from shared import state
from features.recorder.recorder import recorder, RecorderError

router = APIRouter(prefix="/api/recorder", tags=["recorder"])


class ArmRequest(BaseModel):
    trigger: str = "lmb"
    max_s: float = 20
    wide: bool = False


def _run(fn, *args):
    try:
        return fn(*args)
    except RecorderError as e:
        raise HTTPException(e.status, e.detail)


@router.get("")
async def recorder_status():
    return recorder.status()


@router.post("/arm")
def recorder_arm(req: ArmRequest):
    return _run(recorder.arm, state, req.trigger, req.max_s, req.wide)


@router.post("/stop")
def recorder_stop():
    return recorder.stop()


@router.post("/cancel")
def recorder_cancel():
    return recorder.cancel()


@router.get("/result")
async def recorder_result(interval_ms: float = 85.0, shots: Optional[int] = None,
                          lead_ms: float = 0.0):
    return _run(recorder.result, interval_ms, shots, lead_ms)
