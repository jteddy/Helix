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

All real testing is done live on the MAKCU hardware, which Claude does not have. The server starts without the device (MAKCU shows N/C), so the API and UI can be exercised, but device behavior cannot be verified. State exactly what was and wasn't verified; never claim a hardware path works because the code looks right. Report device results the way the vendor does: transport, firmware version, returned bytes and observed physical behavior separately; a host-side test is not hardware proof. There is no test suite or linter.

## Rules

- Commit and push finished fixes to `origin/main` without asking; the user tests from the pushed code. Never force-push, and if `origin/main` has new commits, stop and ask. Never commit `config.json`.
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
- `click_button` must not hold `command_lock` while the button is down: recoil moves wait on that lock, so a held lock stalled compensation for the whole 30 ms hold at every flashlight fire. The `_clicking_button` filter stays set through the hold plus drain instead. On V4.073+ (`_native_click`, set when `km.baud()` answers) the click is a single firmware-timed `km.click(n,1,30)`, with n = 1..5 for LMB, RMB, MMB, M4, M5 (numbering inferred from the V3 reference's `turbo` entry; not yet confirmed on hardware).
- The watchdog must skip pings while `_spray_active` is set. A failed ping clears button states, which the recoil loop reads as an LMB release and corrupts burst history.
- `connect()` runs on a background thread and always starts the watchdog even if the first connect fails, so a MAKCU plugged in after startup still connects.
- Who owns reconnection has flip-flopped (`create_controller(auto_reconnect=...)` vs Helix's own watchdog). It is currently `False` with the watchdog reconnecting. Don't change either without a hardware test.
- The library's listener thread owns the serial port. Never read it yourself, and never send binary (MAK_API) commands through it: every reply byte below 32 is parsed as a button mask and fires phantom button events. Text replies are obtained with `query()`, which hooks the library's line callback (`_process_pending_commands`) and matches a regex; it depends on that private method, so a library change fails it quietly (no reply, not a crash).
- `mouse/makcu.py` wraps `serial.Serial.read` (the library's listener consumes the port, so this is the only place to see raw bytes). The wrapper feeds the frame decoder and keeps the latest non-text frames for the Button Monitor; use that card, not guesses, to learn which stream format a firmware sends.
- The button stream comes in three wire formats: a bare mask byte, `km.`+mask+CRLF, and binary frames `DE AD 03 00 53 kind id state` (newer firmware; kind 1 = mouse, id 0..4 = LMB RMB MMB M4 M5, id and state `FF FF` = overflow, which disables the stream until `km.buttons(1)` is re-sent). The library parses the first two but misreads frames: a right-click comes out as a left-click, and every button event flickers LMB false for an instant, which resets the recoil script to step 1 (`move_mouse_smoothly` interrupts on an LMB drop). `_decode_frames`, called from the `serial.Serial.read` tee, decodes frames itself, sets `_framed`, and from then on `on_button_event` ignores the library's callbacks; overflow clears state and re-enables the stream (at most a few times: `overflow_loop()` stops it when the firmware overflows again immediately). Keep both halves, and use the Button Monitor (`/api/buttons`, `/api/diagnostics`) to learn which format a firmware uses.
- The library's `_handle_button_data` does `print(">>> ", flush=True)` before it fires the button callback. If stdout is broken (hung-up terminal, closed pipe, EIO) the print raises, the library swallows it, and every button event is silently lost (reproduced: frames visible in the Button Monitor, all event counts 0). So Helix replaces `transport._handle_button_data` with `_apply_mask` (no I/O), and `safe_io.install()` at the top of `main.py` makes stdout/stderr unable to raise. Never put prints or other I/O in code the library calls on its listener thread; `lib_mask_calls` / `lib_error` in the report show where the chain breaks.
- `verify_link()` runs after every connect and only reports (`/api/device`); it never disconnects. Any valid reply at the host baud proves the device is at that baud, because the library never checks the switch itself.
- `move_mouse_smoothly` returns True for a zero move, and checks LMB after each step's move rather than before. Returning False means "interrupted or failed"; changing either behavior makes the recoil loop reset forever or produce no movement.

**Firmware compatibility lives in the `makcu` library build, not in Helix.** `install.py` picks stable `makcu==2.3.1` (firmware 3.4) or the `jteddy/makcu-py-lib` `firmware-v3.7` branch. They differ only in the M4/M5 command names (`ms1`/`ms2` vs `side1`/`side2`); a mismatch silently breaks `click_button` (flashlight). `requirements.txt` alone installs the stock build, so a 3.7 setup needs `install.py`. Helix itself only calls `create_controller`, `set_button_callback`, `enable_button_monitoring`, `move`, `press`, `release` and `disconnect`. The library's firmware assumptions are: the legacy binary baud-change frame at connect (never verified by a read-back), the `km.buttons(1)` stream parsed as bare mask bytes (binary frames are decoded by Helix itself, see above), and plain `km.move` / button commands (from V4.041 the firmware's default mouse interpolation is AUTO, which can alter the timing of Helix's ~2.5 ms move cadence; the library cannot change it). Re-check those three assumptions against the references below on any firmware change, and test live before assuming a new firmware works.

**Scripts.**
- Save always writes `.json`. Load prefers `.json` over `.txt`, so a same-named `.json` shadows a hand-edited `.txt`. Delete removes both.
- File delays are ms; in-memory vectors are seconds (conversion happens in the parsers). The CS2 built-ins are already seconds.
- Resolve script paths only via `AppState._resolve_path` (path-traversal guard). Never join user-supplied `game` or `name` yourself.
- `cycle_script` stays inside the loaded script's game folder (root if none); cycling across games was a bug.
- A selected CS2 built-in weapon overrides the loaded script. `workshop_spread` is deliberately never auto-reloaded at startup.
- The pattern recorder reads movement by polling `km.getpos`, because V4 firmware has no mouse-motion stream (`km.axis` and `km.mouse` exist only on V3.x). The tracked position includes injected moves, so the recorder refuses to start while Recoil is ON and aborts if it is turned on; it polls at 100 Hz, not flat out, because heavy text traffic makes the firmware overflow and disable its button-event stream (left-click then never arrives; re-send `km.buttons(1)` to recover, which the recorder does on arm and when done); it resizes `km.screen` only when the "wide range" option is on (default off: the default 1920x1080 allows about ±540 counts) and restores it afterwards; it reads `km.left()` as a fallback left-click trigger when the button stream is silent, and stops after 3 unanswered queries because each miss costs a 50 ms timeout and drags the sample rate down; an armed recorder cancels itself when the page has not polled `/api/recorder` for 15 s (otherwise it keeps querying and re-enabling the stream in the background); the watchdog skips pings while `_recording` is set.

**Web and clients.**
- The browser CSP is set in `main.py` (`add_security_headers`). Any new external script, style, font or image host must be added there or the browser silently blocks it. `/streamdeck/setup` loads marked and DOMPurify from jsdelivr, so it needs internet.
- Script and game names are user-controlled: escape with `escHtml` before putting them in `innerHTML` or attributes.
- The game preset list is duplicated in `menu/games.py` (`GAME_BASE_SENSITIVITIES`) and hard-coded in `index.html`. Update both. The `games` field of `/api/state` is script folders, not presets.
- The Stream Deck plugin polls with a recursive `setTimeout` (its CEF host throttles `setInterval`, which froze icons) and relies on the `no-store` header on `/api/streamdeck`. Don't "simplify" either. `/api/streamdeck` and `/api/health` are filtered out of the uvicorn access log.
- The API has no auth, binds `0.0.0.0` and allows all CORS origins. It is LAN-only by design, so don't add endpoints that would make exposure dangerous (shell, arbitrary file access).

**Restarting from the UI** (`POST /api/server/restart`). `main.py`'s `__main__` block builds `uvicorn.Server(Config(app))` and stores it in `shared.server`; the endpoint sets `shared.restart_requested` and `should_exit`, and after `server.run()` returns the block relaunches. Under systemd (`INVOCATION_ID` set) it exits 75 and relies on the unit's `Restart=always` (or `on-failure`); otherwise it `os.execv`s itself. Keep these facts: pass the app object, never `"main:app"` (the string form re-imports the file as a second module with separate globals); flush before `os.execv` or buffered output is lost; Windows and non-`main.py` launches report `restart_supported: false`; the Origin check exists because CORS is wide open and there is no auth, so any new endpoint with a disruptive effect needs the same guard.

**Config and platforms.** `config.json` stores an absolute `scripts_dir`, so never commit it or copy it between machines. Its save is atomic only on POSIX. Linux and Windows must both keep working: no Linux-only calls in the server or `mouse/` path; `start.sh`, systemd and udev are Linux-only and Windows runs `python main.py`. `cearum-web.service` is a legacy leftover; the real unit is written by `setup-autostart.sh`.

## MAKCU references

Command and wire formats come from these, not from memory, another language's SDK, or an older firmware's behavior. If they disagree with each other or with the code, resolve that before changing device behavior.

- `makcu-docs` MCP (`.mcp.json`, https://makcu.com/mcp): the `km.*` serial command reference with per-firmware notes (`get_command`, `search_docs`). Docs only; it cannot talk to the device.
- Vendor pages: https://makcu.com/en/api/ (V3 reference plus the V4 differences section) and https://makcu.com/api/versions (per-build capability matrix and changelog).
- mak-suite (https://github.com/terrafirma2021/mak-suite), the vendor's SDK and protocol contracts: `protocol/MAK_API.md` (binary), `protocol/KM_API.md` (ASCII), `llm.md` (integration guide). Read them with `gh api repos/terrafirma2021/mak-suite/contents/<path>` or the raw GitHub URL. The MCP endpoint it advertises (https://makxd.com/mcp) redirected to a web page and rejected MCP requests when tried, so it is not registered here.
- Helix uses the third-party `makcu` library only. The vendor's own Python SDK is `makxd` (PyPI, Python 3.10+; source in mak-suite `python/makxd`): typed MAK_API calls, `firmware_version()`, framed `input_stream` events, explicit connection config. It has not been evaluated against Helix. It would be the route to the exact firmware build, interpolation control and physical-button reads, but swapping it in is a large change that needs hardware testing.
- The vendor calls the raw text `km.` button events legacy and the framed `input_stream` (`0x53` frames) the supported contract. Helix still depends on the text `km.buttons(1)` stream, so if button input goes dead on a new firmware, check that first.
- SDK lifecycle rules worth keeping: connect once and reuse the connection, identify the firmware on connect, and release any input you hold down on every exit path, including shutdown.

## Git

Conventional prefixes (`fix:`, `feat:`, `ui:`, `docs:`, `chore:`). Releases are tagged `vX.Y.Z`; the displayed version is `#hdr-ver` in `static/index.html`.
