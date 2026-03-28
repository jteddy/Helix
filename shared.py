"""
Shared singletons — imported by main.py and all routers.
Avoids circular imports by keeping state and save_async in one place.
"""
import asyncio

import config_manager
from state import AppState
from mouse.makcu import makcu_controller  # noqa: F401  (re-exported for routers)

state = AppState()


async def save_async():
    """Persist state to disk without blocking the async event loop."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, config_manager.save, state)
