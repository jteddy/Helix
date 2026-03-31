import json
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from shared import state, makcu_controller

router = APIRouter(tags=["streamdeck"])

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@router.get("/api/streamdeck")
async def streamdeck_state():
    return JSONResponse(
        content={
            "recoil":     state.recoil_enabled,
            "flashlight": state.flashlight_enabled and state.recoil_enabled,
            "makcu":      makcu_controller.is_connected(),
            "script":     state.loaded_script,
        },
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


@router.get("/streamdeck/setup")
async def streamdeck_setup_docs():
    md_path = os.path.join(_BASE_DIR, "streamdeck", "SETUP.md")
    if not os.path.exists(md_path):
        raise HTTPException(404, "streamdeck/SETUP.md not found")
    with open(md_path) as f:
        raw = f.read()
    escaped = json.dumps(raw)
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Stream Deck Setup — Helix</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/dompurify@3/dist/purify.min.js"></script>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Segoe UI',system-ui,sans-serif;background:#0c0c0f;color:#e2e2e8;
       max-width:780px;margin:0 auto;padding:32px 20px 60px;line-height:1.7;}}
  h1,h2,h3{{color:#4d9cff;margin:1.4em 0 .5em;line-height:1.2}}
  h1{{font-size:1.6em;border-bottom:1px solid #232328;padding-bottom:.4em}}
  h2{{font-size:1.2em}} h3{{font-size:1em}}
  p{{margin:.6em 0}}
  code{{font-family:'Space Mono','Courier New',monospace;font-size:.85em;
        background:#111116;border:1px solid #232328;border-radius:4px;padding:1px 5px;color:#4d9cff}}
  pre{{background:#111116;border:1px solid #232328;border-radius:7px;
       padding:14px 16px;overflow-x:auto;margin:1em 0}}
  pre code{{background:none;border:none;padding:0;color:#e2e2e8}}
  a{{color:#4d9cff}}
  ul,ol{{padding-left:1.4em;margin:.5em 0}}
  li{{margin:.25em 0}}
  hr{{border:none;border-top:1px solid #232328;margin:1.5em 0}}
  strong{{color:#e2e2e8}}
</style>
</head><body>
<div id="md"></div>
<script>document.getElementById('md').innerHTML=DOMPurify.sanitize(marked.parse({escaped}));</script>
</body></html>""")
