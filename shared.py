"""
Shared singletons — imported by main.py and all routers.
Avoids circular imports by keeping state and save_async in one place.
"""
import asyncio
import time

import config_manager
from state import AppState
from mouse.makcu import makcu_controller  # noqa: F401  (re-exported for routers)

state = AppState()

# Server lifecycle, written by main.py's __main__ block and read by routers/server.py.
# Lives here (not in main.py) because uvicorn used to import main.py a second time
# as "main", giving the endpoint and the __main__ block different module globals.
server = None              # the uvicorn.Server, or None when not started via `python main.py`
restart_requested = False
started_at = time.time()


async def save_async():
    """Persist state to disk without blocking the async event loop."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, config_manager.save, state)
