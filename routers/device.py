from fastapi import APIRouter

from shared import makcu_controller

router = APIRouter(tags=["device"])


@router.get("/api/device")
async def device_info():
    return makcu_controller.device_summary()
