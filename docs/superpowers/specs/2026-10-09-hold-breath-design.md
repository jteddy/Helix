# Hold Breath — design

Date: 2026-10-09. Status: draft for review.

## Goal

When the player aims (right mouse button by default), Helix makes the MAKCU press the
game's hold-breath key, so the scope steadies without the player pressing it by hand.
It must work whether the game uses hold-to-aim or toggle-aim, and whether its hold
breath is a held key or a toggled one.

## Non-goals

- Per-game profiles. One set of settings; the player flips the switches when changing
  game. Profiles can be added later if switching becomes a chore.
- Re-syncing toggle-ADS when the game leaves ADS without a right-click (sprint, reload,
  inventory). The player right-clicks twice to get back in sync.
- Switching settings from a mouse button.
- Randomised timing.
- The Android app UI (separate repository). It keeps working; it just has no Hold
  Breath controls until it is updated.

## Settings

All global, persisted in `config.json` under `hold_breath`.

| Field | Values | Default | Meaning |
|---|---|---|---|
| `enabled` | bool | `false` | Master switch, toggled like Recoil and Flashlight |
| `trigger` | `RMB`, `MMB`, `M4`, `M5` | `RMB` | Mouse button that aims (LMB is excluded: it fires) |
| `ads_mode` | `hold`, `toggle` | `hold` | How the game aims: while the button is held, or each click flips aiming |
| `breath_mode` | `hold`, `toggle` | `hold` | How the game's hold breath works: key held down, or tap on / tap off |
| `key` | key name from `mouse/keys.py`, or `NONE` | `NONE` | The game's hold-breath key, stored as the canonical name |
| `tap_on_release` | bool | `false` | Toggle breath only: tap the key again when aiming ends |
| `delay_ms` | 0–2000 | `0` | Wait this long after aiming starts before starting hold breath (scope-in) |
| `max_hold_ms` | 0–30000 | `0` | Stop hold breath after this long while still aiming; `0` = no limit |

## Behaviour

**Active** means: `enabled` and Recoil enabled and `key` is not `NONE` and the MAKCU is
connected. Like the Flashlight, Recoil being ON keeps it out of menus and the desktop.

**Aiming**
- `ads_mode = hold`: aiming while the trigger button is held.
- `ads_mode = toggle`: every press of the trigger button flips aiming. Aiming resets to
  "not aiming" whenever Hold Breath becomes inactive or the trigger or ADS mode changes.

**Breath** is a small state machine:

| From | Event | To | Key action |
|---|---|---|---|
| IDLE | aiming starts | WAITING | none (start the delay clock) |
| WAITING | aiming ends | IDLE | none |
| WAITING | delay elapsed | BREATHING | hold: key down. toggle: tap |
| BREATHING | max hold elapsed (if > 0) | SPENT | hold: key up. toggle: tap |
| BREATHING | aiming ends | IDLE | hold: key up. toggle: tap if `tap_on_release` |
| SPENT | aiming ends | IDLE | none |
| any | becomes inactive, or `key` / `breath_mode` / `trigger` / `ads_mode` changes | IDLE | if BREATHING: as for "aiming ends", using the old key |

A tap is a 30 ms press, the same as the Flashlight Key. Changing `delay_ms`,
`max_hold_ms` or `tap_on_release` does not interrupt a breath in progress; the new
values apply from the next step. The header card and `/ws` show "active" as enabled and
Recoil ON, like the Flashlight card, even when no key is bound.

Each key action is logged once, for example
`[HoldBreath] down leftshift` and `[HoldBreath] up leftshift`.

## Architecture

Three new units, each testable on its own.

1. **`features/holdbreath/machine.py`**: `HoldBreathMachine`, pure logic with no I/O, no
   threads and no globals. `step(now, trigger_down, active, cfg) -> list[Action]`, where
   an action is `("down" | "up" | "tap", key)` and `cfg` is an immutable snapshot of the
   settings. It compares `cfg` with the previous step's to detect setting changes.
2. **`features/holdbreath/holdbreath.py`**: the loop thread, started in `main.py`'s
   lifespan next to the Recoil and Flashlight loops. Every 5 ms it reads a settings
   snapshot, the Recoil switch, the trigger button state and the connection, steps the
   machine, and hands each action to the keyboard queue. When the device controller
   changes (first connect or a reconnect) it sends key up for the configured key and
   resets the machine, so a key left down by a crash, a kill or a dropped link is
   released.
3. **`mouse/keyboard.py`**: `KeyboardQueue`, one worker thread that sends every keyboard
   command in order: `tap(key, hold_ms)`, `down(key)`, `up(key)`, `release_all()`. It
   takes a `send(cmd) -> bool` callable (in Helix, `makcu_controller.send_text`), so tests
   use a fake. After a tap it waits `hold_ms` + 15 ms before sending the next command,
   because the firmware runs one timed press at a time and answers `ERR` to a key command
   sent during one. It tracks keys it holds down; `release_all()` sends key up for each.
   Commands are `km.press(<usage>,<ms>)`, `km.down(<usage>)` and `km.up(<usage>)` with
   the numeric HID usage from `mouse/keys.py`.

**Flashlight change:** `makcu_controller.press_key()` sends through the same queue
(`tap(key, 30)`) instead of calling `send_text` directly, so a flashlight tap and a
hold-breath key down can never overlap.

**Shutdown:** the lifespan exit calls `keyboard.release_all()` and lets the queue drain
before `makcu_controller.disconnect()`.

**Disconnect while breathing:** the machine sees "inactive" and emits key up; the send
fails and is dropped. On reconnect the loop sends key up again (point 2 above).

**Mouse buttons:** the trigger state comes from the existing button stream (`km.`+mask
text on V4.073, decoded by Helix). If the Flashlight mouse button equals the trigger,
the Flashlight's programmatic clicks are filtered out of the stream as today, so they
do not toggle aiming.

## State and API

**State:** `AppState` gains the `hold_breath` fields (`__init__`, `to_dict`, `from_dict`
with the defaults above; a config without the section loads the defaults), a snapshot
getter `get_hold_breath()` and `toggle_hold_breath()`.

**API (additive only):**
- `GET /api/state` adds a `hold_breath` object with the fields above.
- `POST /api/hold_breath`: partial update of any field. Out-of-range or unknown values
  return 400 with a message and change nothing.
- `POST /api/hold_breath/toggle` returns `{"enabled": bool}`.
- `/ws` adds `hold_breath_enabled`, `hold_breath_active` (enabled and Recoil ON) and
  `hold_breath_ads_mode`.
- `GET /api/streamdeck` adds `hold_breath` (enabled and Recoil ON) and
  `hold_breath_ads` (`hold` or `toggle`).
- `GET /api/diagnostics` adds the `hold_breath` settings.

**Client impact:** existing fields and endpoints are unchanged. Old Stream Deck plugin
versions ignore the new keys. The Android app ignores the new fields and has no Hold
Breath controls until it is updated.

## UI (`static/index.html`)

- **New "Hold Breath" tab** between Flashlight and Tools.
  - Control card: Enable switch; Trigger Button select; **ADS: Hold / Toggle**;
    **Breath key: Hold / Toggle**; "Tap again when aiming ends" (shown only for toggle
    breath); Hold Breath Key with press-to-bind and Clear. The Flashlight Key's binding
    code becomes a shared helper used by both.
  - Timing card: Delay after aiming (ms); Max hold (ms, 0 = no limit).
  - Note: only active while Recoil is ON; in toggle-ADS games, if Helix gets out of
    step, right-click twice.
- **Header:** three cards across, Recoil | Flashlight | Hold Breath, with the Script row
  underneath. The Hold Breath card shows ON/OFF (enabled and Recoil ON), a
  "Master: ON/OFF" line and the ADS mode; tapping it toggles the master switch. The
  layout is checked at 390 px and desktop width.

## Stream Deck plugin

- New action `com.helix.holdbreath`, "Toggle Hold Breath": key press posts
  `/api/hold_breath/toggle`; the icon is drawn live from `/api/streamdeck`, showing
  ON/OFF and "HOLD" or "TOGGLE".
- `manifest.json`: the action, static `holdbreath-on.svg` and `holdbreath-off.svg`, and
  version 1.0.0 to 1.1.0. The plugin folder has to be copied to the Stream Deck PC again.
- `streamdeck/SETUP.md`: the new action.

## Errors

- Invalid settings: 400 with the reason; the UI shows it and keeps the previous value.
- Keyboard command while disconnected: dropped and logged; reconnect releases the key.
- A firmware `ERR` is not detected (commands are fire-and-forget); the queue's spacing
  is what prevents it. Documented as a known limit.

## Testing

- **Host, no device; `config.json` untouched and checksummed:**
  - State machine with a fake clock: every transition in the table, for both ADS modes
    and both breath modes, delay, max hold, `tap_on_release`, going inactive while
    breathing, a key change while breathing, and toggle-ADS counting and reset.
  - Keyboard queue with a fake `send`: order kept, spacing after a tap, held-key
    tracking, `release_all`.
  - Settings persistence round trip, and an old config without `hold_breath`.
  - Router validation and partial updates (FastAPI TestClient, `save_async` stubbed).
  - Loop integration with stubbed buttons and queue: right-click in, right-click out.
- **Headless Chromium against the live page, all writes intercepted:** tab controls and
  their POST bodies, key binding, "tap again" visibility, header card and its tap,
  screenshots at 390 px and desktop width. Existing UI tests still pass.
- **Stream Deck:** manifest is valid JSON; `plugin.js` loaded in headless Chromium with a
  fake Stream Deck socket draws the new icon and posts the right endpoint.
- **Live server after restart:** `/api/state`, `/api/streamdeck` and `/ws` carry the new
  fields; bad values return 400; the log is clean.
- **Hardware (player):**
  - First, the Flashlight Key test: confirms `km.press` reaches the gaming PC.
  - Then, in game with ADS Hold and Breath Hold: the log shows `down` and `up` around
    each aim, and the scope steadies.
  - Repeat with the toggle modes in a game that uses them.

## Documentation

README (Hold Breath tab, header cards, API reference, Stream Deck), `streamdeck/SETUP.md`,
and CLAUDE.md gotchas (the keyboard queue and why, release on connect and shutdown).

## Risks

- Keyboard injection has not been confirmed on this hardware: the Flashlight Key is
  untested, and `km.down` / `km.up` come from the vendor's KM_API document, not a test.
- Firmware `ERR` replies are not detected.
- Toggle-ADS can get out of step (accepted; right-click twice).
- A key can stay down on the gaming PC from a hard kill until Helix next connects to the
  MAKCU, which releases it.

## Rollback

All changes are additive. If it does not work, `git revert` the feature commits.
