from fastapi import APIRouter

from shared import makcu_controller

router = APIRouter(tags=["device"])


@router.get("/api/device")
async def device_info():
    return makcu_controller.device_summary()


@router.get("/api/device/rx")
async def device_rx():
    """Last raw bytes from the device. Open while holding left-click to see the
    button-stream format the firmware really sends."""
    return makcu_controller.rx_tail()
