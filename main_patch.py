"""
main.py — PATCH for Bug 7
=========================
Find the save_pattern route (POST /api/patterns/{game}/{weapon}) and add
the missing `await _save_async()` call so that loading a pattern via the
Vector Editor is persisted to config.json.

BEFORE:
-------
@app.post("/api/patterns/{game}/{weapon}")
async def save_pattern(game: str, weapon: str, request: Request):
    body = await request.body()
    content = body.decode()
    state.save_script(weapon, content, game)
    full_name = f"{game}/{weapon}"
    if state.loaded_script in (full_name, weapon):
        state.load_script(weapon, game)
    return {"saved": True}


AFTER (add the two lines marked with # FIX 7):
----------------------------------------------
@app.post("/api/patterns/{game}/{weapon}")
async def save_pattern(game: str, weapon: str, request: Request):
    body = await request.body()
    content = body.decode()
    state.save_script(weapon, content, game)
    full_name = f"{game}/{weapon}"
    if state.loaded_script in (full_name, weapon):
        state.load_script(weapon, game)
    await _save_async()   # FIX 7: persist config so loaded_script survives restart
    return {"saved": True}


No other changes to main.py are required.
"""
