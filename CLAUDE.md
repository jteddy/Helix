# Helix

FastAPI server (Linux and Windows) that drives a MAKCU USB HID device to run recoil-compensation and flashlight loops. Controlled from a single-file web UI, a Stream Deck plugin, and a separate Android app.

Install, run, autostart (systemd) and launcher instructions, plus the feature and API reference, live in `README.md` (Quick Start, Auto-start on Boot, Desktop Launcher, API Reference). Don't duplicate them here. If README and code disagree, the code wins; fix the README.

## Architecture (high level)

- `main.py`: app, lifespan, `/ws` broadcast. Starts the MAKCU connection and the recoil and flashlight loops on daemon threads, plus asyncio broadcast and autosave tasks.
- `state.py`: `AppState`, the one shared lock-protected settings object, which also owns script load/save. The instance is created in `shared.py`.
- `routers/`: thin HTTP handlers that mutate `state` and persist it.
- `features/`: the long-running loops (recoil, flashlight), the pattern recorder, and built-in CS2 patterns.
- `mouse/makcu.py`: all device I/O, as a class of static methods with its own locks and a reconnect watchdog.
- `static/index.html`: the entire UI (inline CSS/JS, no build step).
- `streamdeck/`: plugin that polls `/api/streamdeck`.
- `saved_scripts/<game>/<weapon>`: recoil patterns shared by the Scripts panel and the Tools tab.
- `config.json`: runtime settings, autosaved, gitignored.

The web UI, Stream Deck plugin and Android app (separate private repo, not available here) all consume the same REST + `/ws` contract.

## Verification

All real testing is done live on the MAKCU hardware, which Claude does not have. The server starts without the device (MAKCU shows N/C), so the API and UI can be exercised, but device behavior cannot be verified. State exactly what was and wasn't verified; never claim a hardware path works because the code looks right. There is no test suite or linter.

## Rules

- Commit finished work without asking. Never push unless asked. Never commit `config.json`.
- Don't edit, retune or delete anything in `saved_scripts/` unless asked. The patterns are hand-tuned.
- The REST API and `/ws` payload are a contract with three clients. Before changing, renaming or removing an endpoint, field or message shape (including the `/api/streamdeck` keys), call out the Stream Deck and Android impact. Prefer additive changes.

## Gotchas

**Adding or changing a setting touches many places.** `AppState.__init__`, `to_dict` and `from_dict` (defaults are duplicated; keep them in sync, and a missing `from_dict` entry silently isn't persisted), the router's update model, `_broadcast_loop` if clients need it live, `static/index.html`, the README API reference, and the Stream Deck and Android clients if exposed.

**`/ws` is a hand-built subset of state.** It is pushed every 200 ms but only when a single global hash changes, and inbound messages are ignored. A client that connects between changes gets nothing, so clients must `GET /api/state` on load. UI changes go through REST, not the socket.

**State and locking.** All settings access goes through `AppState._lock` (an RLock). Loops use the getters, which return snapshots; read patterns only via `get_active_vectors()` or `get_vectors()`, because a script load mid-spray mutates the live list. Use the atomic `toggle_*` methods. Never do device I/O while holding the lock: device calls can block for seconds and would stall HTTP and the broadcast.

**Device layer (`mouse/makcu.py`).**
- Take `command_lock` only through `_acquire_command_lock()`. Its 3 s timeout marks the device disconnected instead of hanging the server (a hung USB device once blocked the server for hours).
- Snapshot `controller` under `connection_lock` and check it is still the same object before sending; the watchdog can null it between `is_connected()` and the call.
- Leave button monitoring ON during programmatic clicks. Toggling it loses physical LMB-release events and desyncs the firmware; the `_clicking_button` filter drops the firmware's re-reported events instead.
- The watchdog must skip pings while `_spray_active` is set. A failed ping clears button states, which the recoil loop reads as an LMB release and corrupts burst history.
- `connect()` runs on a background thread and always starts the watchdog even if the first connect fails, so a MAKCU plugged in after startup still connects.
- Who owns reconnection has flip-flopped (`create_controller(auto_reconnect=...)` vs Helix's own watchdog). It is currently `False` with the watchdog reconnecting. Don't change either without a hardware test.
- The library's listener thread owns the serial port. Never read it yourself, and never send binary (MAK_API) commands through it: every reply byte below 32 is parsed as a button mask and fires phantom button events. Text replies are obtained with `query()`, which hooks the library's line callback (`_process_pending_commands`) and matches a regex; it depends on that private method, so a library change fails it quietly (no reply, not a crash).
- `verify_link()` runs after every connect and only reports (`/api/device`); it never disconnects. Any valid reply at the host baud proves the device is at that baud, because the library never checks the switch itself.
- `move_mouse_smoothly` returns True for a zero move, and checks LMB after each step's move rather than before. Returning False means "interrupted or failed"; changing either behavior makes the recoil loop reset forever or produce no movement.

**Firmware compatibility lives in the `makcu` library build, not in Helix.** `install.py` picks stable `makcu==2.3.1` (firmware 3.4) or the `jteddy/makcu-py-lib` `firmware-v3.7` branch. They differ only in the M4/M5 command names (`ms1`/`ms2` vs `side1`/`side2`); a mismatch silently breaks `click_button` (flashlight). `requirements.txt` alone installs the stock build, so a 3.7 setup needs `install.py`. Helix itself only calls `create_controller`, `set_button_callback`, `enable_button_monitoring`, `move`, `press`, `release` and `disconnect`. The library's firmware assumptions are: the legacy binary baud-change frame at connect (never verified by a read-back), the `km.buttons(1)` stream parsed as bare mask bytes, and plain `km.move` / button commands (from V4.041 the firmware's default mouse interpolation is AUTO, which can alter the timing of Helix's ~2.5 ms move cadence; the library cannot change it). The vendor reference is https://makcu.com/en/api/ (it has a per-build V4 differences section); re-check those three assumptions against it on any firmware change, and test live before assuming a new firmware works.

**Scripts.**
- Save always writes `.json`. Load prefers `.json` over `.txt`, so a same-named `.json` shadows a hand-edited `.txt`. Delete removes both.
- File delays are ms; in-memory vectors are seconds (conversion happens in the parsers). The CS2 built-ins are already seconds.
- Resolve script paths only via `AppState._resolve_path` (path-traversal guard). Never join user-supplied `game` or `name` yourself.
- `cycle_script` stays inside the loaded script's game folder (root if none); cycling across games was a bug.
- A selected CS2 built-in weapon overrides the loaded script. `workshop_spread` is deliberately never auto-reloaded at startup.
- The pattern recorder reads movement by polling `km.getpos`, because V4 firmware has no mouse-motion stream (`km.axis` and `km.mouse` exist only on V3.x). The tracked position includes injected moves, so the recorder refuses to start while Recoil is ON and aborts if it is turned on; it enlarges `km.screen` to avoid edge clamping and restores it afterwards; the watchdog skips pings while `_recording` is set.

**Web and clients.**
- The browser CSP is set in `main.py` (`add_security_headers`). Any new external script, style, font or image host must be added there or the browser silently blocks it. `/streamdeck/setup` loads marked and DOMPurify from jsdelivr, so it needs internet.
- Script and game names are user-controlled: escape with `escHtml` before putting them in `innerHTML` or attributes.
- The game preset list is duplicated in `menu/games.py` (`GAME_BASE_SENSITIVITIES`) and hard-coded in `index.html`. Update both. The `games` field of `/api/state` is script folders, not presets.
- The Stream Deck plugin polls with a recursive `setTimeout` (its CEF host throttles `setInterval`, which froze icons) and relies on the `no-store` header on `/api/streamdeck`. Don't "simplify" either. `/api/streamdeck` and `/api/health` are filtered out of the uvicorn access log.
- The API has no auth, binds `0.0.0.0` and allows all CORS origins. It is LAN-only by design, so don't add endpoints that would make exposure dangerous (shell, arbitrary file access).

**Config and platforms.** `config.json` stores an absolute `scripts_dir`, so never commit it or copy it between machines. Its save is atomic only on POSIX. Linux and Windows must both keep working: no Linux-only calls in the server or `mouse/` path; `start.sh`, systemd and udev are Linux-only and Windows runs `python main.py`. `cearum-web.service` is a legacy leftover; the real unit is written by `setup-autostart.sh`.

## Git

Conventional prefixes (`fix:`, `feat:`, `ui:`, `docs:`, `chore:`). Releases are tagged `vX.Y.Z`; the displayed version is `#hdr-ver` in `static/index.html`.
