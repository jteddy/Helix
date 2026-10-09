# Hold Breath Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the player aims (RMB by default), Helix makes the MAKCU press the game's hold-breath key, for games with hold or toggle aiming and hold or toggle hold-breath.

**Architecture:** A pure state machine (`features/holdbreath/machine.py`) decides key actions from "trigger down?", "active?", settings and time. A 5 ms loop thread (`features/holdbreath/holdbreath.py`) feeds it and sends its actions through a new keyboard queue (`mouse/keyboard.py`) that every keyboard command, including the existing Flashlight Key, goes through, so the firmware never sees overlapping key commands. Settings live in `AppState` and are exposed through a new `/api/hold_breath` router, `/ws`, `/api/streamdeck`, a new UI tab, a header card and a Stream Deck action.

**Tech Stack:** Python 3.13, FastAPI, the third-party `makcu` library (serial), single-file web UI (`static/index.html`, inline JS/CSS, no build), Stream Deck SDK v2 plugin (plain JS). Tests: pytest (host), headless Chromium driven over the DevTools protocol with Python `websockets` (UI and plugin).

**Spec:** `docs/superpowers/specs/2026-10-09-hold-breath-design.md`. Read it before starting; this plan implements it.

---

## Context for a fresh session (read first)

You are working in `/home/jason/Downloads/final/Helix` on the host `mini`, which is also where the Helix server runs and where the MAKCU is plugged in. Read `CLAUDE.md` in the repo root before touching code; its rules apply to every task.

**Environment facts (verified 2026-10-09):**
- The server runs from this checkout under the systemd unit `helix` (User `jason`), port 8000. After a Python change, restart it with `curl -s -X POST localhost:8000/api/server/restart`. It exits 75 and systemd relaunches it in about 6–10 s. Then wait with `for i in $(seq 1 30); do sleep 1; curl -sf localhost:8000/api/device >/dev/null && break; done`. `static/index.html` is read from disk on every request, so UI-only changes need no restart; just reload.
- Logs: `journalctl -u helix --since "-2min" --no-pager`. Live state: `curl -s localhost:8000/api/state`, `curl -s localhost:8000/api/diagnostics`.
- MAKCU firmware V4.073 at 4,000,000 baud. Button events arrive as `km.`+mask byte+CRLF and are decoded by Helix (`_decode_text_masks` in `mouse/makcu.py`); LMB, RMB, MMB, M4 and M5 events were all verified live. `makcu_controller.get_button_state(name)` takes `"LMB" | "RMB" | "MMB" | "M4" | "M5"`.
- The Flashlight Key (commit `92a8204`) sends `km.press(<HID usage>,30)`. **It has NOT been confirmed on hardware** (the user has not yet tested whether the key arrives on the gaming PC). Hold Breath depends on the same keyboard path plus `km.down`/`km.up`. Build anyway (the user asked), but say so plainly in the final report and ask the user to run the Flashlight Key test.
- Vendor command reference (mak-suite `protocol/KM_API.md`): `km.down(key)`, `km.up(key)`, `km.press(key[,hold_ms[,random_range]])`; `key` may be a decimal HID usage 0–255. A successful mutation returns no bytes; an error returns `ERR`. "Only one timed press or string action can be active at a time"; another press, string, down, up, multidown or multiup request "can return ERR while that action is active". That is why the keyboard queue exists.
- `mouse/keys.py` already exists (from the Flashlight Key work): `normalize_key(name) -> canonical name or None`, `key_usage(name) -> int or None`. Examples: `f`→9, `f1`→58, `space`→44, `shift`/`leftshift`→225, `ctrl`→224.
- `pytest` 9, `websockets` 16 and `/usr/bin/chromium-browser` are installed. No new dependencies are needed.

**Plan validation (2026-10-09):** the code in Tasks 1–6 was applied, using this plan's own edit anchors, to a throwaway copy of the repo, and the plan's own tests were run against it: 56/56 host tests, 23/23 UI tests (page served from the copy, GETs forwarded to the live server), 5/5 Stream Deck tests. The header and the new tab were checked by screenshot at 390 px and 1100 px. Each anchor matched exactly once. Still follow the TDD steps (run each test red first, then green); the repo may have moved since.

**Decisions already made with the user (do not reopen):**
- No per-game profiles. One global set of settings.
- Trigger button selectable: RMB (default), MMB, M4, M5. LMB is excluded (it fires).
- Enable switch like Recoil and Flashlight; only acts while Recoil is ON.
- ADS: Hold / Toggle. Breath key: Hold / Toggle, plus "Tap again when aiming ends" (toggle breath only, default off).
- Delay after aiming (0–2000 ms) and Max hold (0–30000 ms, 0 = no limit). No randomisation.
- Toggle-ADS desync is not handled (the user right-clicks twice).
- Header gets a third tap card (Recoil | Flashlight | Hold Breath). Stream Deck gets one new action, "Toggle Hold Breath", whose icon shows ON/OFF and HOLD/TOGGLE.
- If it does not work on hardware, the user will `git revert` the commits.

**Scratch area:** put every test file and tool in this session's scratchpad directory (given in your system prompt; below it is `$S`). Do not add tests to the repo; it has no test suite by design. Create `$S/tests` for pytest files and `$S/ui` for browser tests.

**Safety rules for testing (from the user's setup):**
- Host tests must never open the serial port (never call `makcu_controller.connect()`), never write the real `config.json` (the conftest below redirects it and checks it), and never send real keyboard or mouse commands.
- Browser tests run against the live page but intercept every non-GET request inside the page, so nothing on the live server changes.
- Live checks may read anything and may POST invalid values (which change nothing), but must not POST valid Hold Breath or Flashlight changes, and must not toggle anything. A real key press would type on the user's gaming PC.

## Global Constraints

- API changes are additive only: no existing endpoint, field or `/ws` key is renamed or removed (CLAUDE.md: three clients depend on them).
- Keyboard commands go only through the `KeyboardQueue` in `mouse/keyboard.py`, using numeric HID usages: tap = `km.press(<usage>,30)`, `km.down(<usage>)`, `km.up(<usage>)`. Queue waits `hold_ms + 15` ms after a tap.
- Settings ranges: `trigger` ∈ {`RMB`,`MMB`,`M4`,`M5`}; `ads_mode`, `breath_mode` ∈ {`hold`,`toggle`}; `key` = canonical name from `mouse/keys.py` or `NONE`; `delay_ms` 0–2000; `max_hold_ms` 0–30000 (0 = no limit). Invalid values → HTTP 400 and nothing changes.
- Defaults: `enabled` false, `trigger` RMB, `ads_mode` hold, `breath_mode` hold, `key` NONE, `tap_on_release` false, `delay_ms` 0, `max_hold_ms` 0.
- Linux and Windows must both keep working: no Linux-only calls in the server or `mouse/` path.
- Never do device I/O while holding `AppState._lock`. Never put prints or I/O in code the `makcu` library calls on its listener thread (the Hold Breath loop runs on its own thread, so its prints are fine).
- Never commit `config.json`; never touch `saved_scripts/` (the working tree has unrelated user changes there; stage files by name, never `git add -A` or `git add .`).
- Commit after each task with a conventional prefix (`feat:`, `fix:`, `ui:`, `docs:`, `chore:`) and this trailer line: `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>` (use the model name and attribution line your own system prompt gives, if different). Before each push run `git fetch -q origin && git log --oneline HEAD..origin/main`; if it prints anything, stop and ask the user. Push with `git push -q origin main`. Never force-push.

## Review Focus

1. **A key stays held down on the gaming PC after a crash, kill, restart or dropped USB link.** Expected: the next connect releases it. Test: Task 4 `test_connect_and_reconnect_release_the_key`; Task 1 `test_release_all_sends_up_for_held_keys`.
2. **A flashlight tap and a hold-breath key-down happen at the same moment.** Expected: both arrive, never overlapping (no firmware `ERR`). Test: Task 1 `test_tap_waits_before_next_command` and `test_press_key_goes_through_queue`.
3. **A POST with one valid and one invalid field.** Expected: 400 and nothing changes (no half-applied settings). Test: Task 2 `test_invalid_update_changes_nothing`.
4. **Changing key, breath mode, trigger or ADS mode while aiming, or Recoil turning off mid-aim.** Expected: the old key is released at once. Test: Task 3 `test_key_change_*`, `test_breath_mode_change_*`, `test_trigger_change_*`, `test_inactive_*`; Task 4 `test_recoil_off_mid_aim_releases`.
5. **Upgrading: an existing `config.json` with no `hold_breath` section.** Expected: loads with the defaults, nothing else changes. Test: Task 2 `test_old_config_without_hold_breath`.

## File map

| File | Status | Responsibility |
|---|---|---|
| `mouse/keyboard.py` | create | `KeyboardQueue`: ordered keyboard commands, tap spacing, held-key tracking |
| `mouse/makcu.py` | modify | create the shared `keyboard` queue; `press_key` uses it |
| `state.py` | modify | `hb_*` settings, `get_hold_breath()`, `toggle_hold_breath()`, persistence |
| `routers/holdbreath.py` | create | `POST /api/hold_breath`, `POST /api/hold_breath/toggle`, validation |
| `routers/streamdeck.py` | modify | `hold_breath`, `hold_breath_ads` keys |
| `routers/diagnostics.py` | modify | `hold_breath` settings in the report |
| `main.py` | modify | include router; `_ws_payload()` with new keys; start loop; release keys on shutdown |
| `features/holdbreath/__init__.py` | create | empty package marker |
| `features/holdbreath/machine.py` | create | `HoldBreathConfig`, `HoldBreathMachine` (pure logic) |
| `features/holdbreath/holdbreath.py` | create | `run_hold_breath()` loop thread |
| `static/index.html` | modify | Hold Breath tab, header card, shared key-binding helper |
| `streamdeck/com.helix.sdPlugin/manifest.json`, `plugin.js`, `icons/holdbreath-on.svg`, `icons/holdbreath-off.svg` | modify/create | Toggle Hold Breath action |
| `README.md`, `streamdeck/SETUP.md`, `CLAUDE.md` | modify | documentation |

---

### Task 1: Keyboard queue, and Flashlight Key through it

**Files:**
- Create: `mouse/keyboard.py`
- Modify: `mouse/makcu.py` (imports at top; `press_key` ~line 359; new module-level line at the end of the file)
- Test: `$S/tests/conftest.py`, `$S/tests/test_keyboard.py`

**Interfaces:**
- Consumes: `mouse.keys.key_usage(name) -> int | None`; `makcu_controller.send_text(cmd) -> bool` (existing; writes `cmd + "\r\n"` under the command lock; returns False when disconnected).
- Produces:
  - `mouse.keyboard.KeyboardQueue(send, sleep=time.sleep)` with `tap(key, hold_ms=30) -> bool`, `down(key) -> bool`, `up(key) -> bool`, `release_all() -> None`, `held() -> set[int]`, `drain(timeout=1.0) -> bool`. `key` is any name `key_usage` accepts; unknown names return False and send nothing.
  - `mouse.makcu.keyboard`: the one shared `KeyboardQueue`, sending through `makcu_controller.send_text`.
  - `makcu_controller.press_key(name) -> bool` now queues a tap instead of sending directly.

- [ ] **Step 1: Create the test scaffolding (shared by all host tests)**

`$S/tests/conftest.py`:

```python
"""Shared setup for host tests. Keeps the real config.json and the device untouched."""
import hashlib
import os
import sys
import tempfile

import pytest

HELIX = "/home/jason/Downloads/final/Helix"
sys.path.insert(0, HELIX)

import config_manager  # noqa: E402

# Any save during tests goes to a temp file, never the live server's config.json.
config_manager.CONFIG_PATH = os.path.join(tempfile.mkdtemp(), "config.json")

_REAL_CFG = os.path.join(HELIX, "config.json")


def _digest():
    if not os.path.exists(_REAL_CFG):
        return None
    with open(_REAL_CFG, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


@pytest.fixture(scope="session", autouse=True)
def real_config_untouched():
    before = _digest()
    yield
    # The live server autosaves every 30 s; if the user changed a setting meanwhile this
    # can trip. Re-run once before suspecting a test.
    assert _digest() == before, "the real config.json changed during the test run"
```

Run every host test from the repo root with `-s` (main.py replaces stdout/stderr when imported, which clashes with pytest's capture):
`cd /home/jason/Downloads/final/Helix && python3 -m pytest -q -s $S/tests`

- [ ] **Step 2: Write the failing tests**

`$S/tests/test_keyboard.py`:

```python
import threading

from mouse.keyboard import KeyboardQueue


class Recorder:
    """Fake device: records sends and waits in order, without real sleeping."""
    def __init__(self):
        self.log = []
        self.lock = threading.Lock()

    def send(self, cmd):
        with self.lock:
            self.log.append(("send", cmd))
        return True

    def sleep(self, s):
        with self.lock:
            self.log.append(("wait", round(s, 3)))


def make():
    r = Recorder()
    return r, KeyboardQueue(r.send, sleep=r.sleep)


def test_commands_use_hid_usages():
    r, kq = make()
    assert kq.tap("f") and kq.down("Shift") and kq.up("leftshift")
    assert kq.drain()
    assert r.log == [("send", "km.press(9,30)"), ("wait", 0.045),
                     ("send", "km.down(225)"), ("send", "km.up(225)")]


def test_tap_waits_before_next_command():
    r, kq = make()
    kq.tap("f", 30)
    kq.down("leftshift")
    assert kq.drain()
    # The wait after the tap must come before the key-down is sent.
    assert r.log.index(("wait", 0.045)) < r.log.index(("send", "km.down(225)"))


def test_custom_hold():
    r, kq = make()
    kq.tap("f1", 50)
    assert kq.drain()
    assert r.log == [("send", "km.press(58,50)"), ("wait", 0.065)]


def test_unknown_key_sends_nothing():
    r, kq = make()
    assert kq.tap("nope") is False and kq.down("") is False and kq.up("f13") is False
    assert kq.drain()
    assert r.log == []


def test_held_tracking_and_release_all_sends_up_for_held_keys():
    r, kq = make()
    kq.down("leftshift")
    kq.down("f")
    assert kq.held() == {225, 9}
    kq.up("f")
    assert kq.held() == {225}
    kq.release_all()
    assert kq.held() == set()
    assert kq.drain()
    assert r.log[-1] == ("send", "km.up(225)")
    assert r.log.count(("send", "km.up(225)")) == 1


def test_release_all_with_nothing_held_sends_nothing():
    r, kq = make()
    kq.release_all()
    assert kq.drain()
    assert r.log == []


def test_send_failure_does_not_stop_the_queue():
    sent = []

    def flaky(cmd):
        sent.append(cmd)
        if cmd.startswith("km.down"):
            raise RuntimeError("boom")
        return True

    kq = KeyboardQueue(flaky, sleep=lambda s: None)
    kq.down("f")
    kq.up("f")
    assert kq.drain()
    assert sent == ["km.down(9)", "km.up(9)"]


def test_press_key_goes_through_queue(monkeypatch):
    from mouse import makcu as M
    sent = []
    monkeypatch.setattr(M.makcu_controller, "send_text", lambda cmd: sent.append(cmd) or True)
    monkeypatch.setattr(M.makcu_controller, "is_connected", lambda: True)
    assert M.makcu_controller.press_key("f") is True
    assert M.keyboard.drain(2.0)
    assert sent == ["km.press(9,30)"]
    assert M.makcu_controller.press_key("nope") is False


def test_press_key_when_disconnected_sends_nothing(monkeypatch):
    from mouse import makcu as M
    sent = []
    monkeypatch.setattr(M.makcu_controller, "send_text", lambda cmd: sent.append(cmd) or True)
    monkeypatch.setattr(M.makcu_controller, "is_connected", lambda: False)
    assert M.makcu_controller.press_key("f") is False
    assert M.keyboard.drain(2.0)
    assert sent == []
```

- [ ] **Step 3: Run the tests and confirm they fail**

Run: `cd /home/jason/Downloads/final/Helix && python3 -m pytest -q -s $S/tests/test_keyboard.py`
Expected: errors with `ModuleNotFoundError: No module named 'mouse.keyboard'`.

- [ ] **Step 4: Create `mouse/keyboard.py`**

```python
"""One queue for every keyboard command Helix sends to the MAKCU.

The firmware runs one timed key action (km.press or km.string) at a time and answers
ERR to another key command (press, string, down, up, multidown, multiup) sent while one
is running (mak-suite protocol/KM_API.md, "Timing"). Helix does not read those replies,
so it never overlaps them instead: commands go out in order from one worker thread, and
after a tap the worker waits out the hold before sending the next. The queue also
remembers which keys it holds down, so they can be released on shutdown."""
import queue
import threading
import time

from mouse.keys import key_usage

TAP_MARGIN_MS = 15   # extra wait after a tap's hold before the next key command


class KeyboardQueue:
    def __init__(self, send, sleep=time.sleep):
        """send(cmd) -> bool writes one text command (without CR/LF) to the device."""
        self._send = send
        self._sleep = sleep
        self._q = queue.Queue()
        self._lock = threading.Lock()
        self._held = set()      # HID usages Helix is holding down
        self._pending = 0       # commands queued or being sent
        threading.Thread(target=self._run, daemon=True, name="keyboard").start()

    def tap(self, key, hold_ms=30):
        """Press and release `key` (firmware-timed km.press). False if the name is unknown."""
        usage = key_usage(key)
        if usage is None:
            return False
        hold_ms = int(hold_ms)
        self._put(f"km.press({usage},{hold_ms})", (hold_ms + TAP_MARGIN_MS) / 1000.0)
        return True

    def down(self, key):
        usage = key_usage(key)
        if usage is None:
            return False
        with self._lock:
            self._held.add(usage)
        self._put(f"km.down({usage})", 0.0)
        return True

    def up(self, key):
        usage = key_usage(key)
        if usage is None:
            return False
        with self._lock:
            self._held.discard(usage)
        self._put(f"km.up({usage})", 0.0)
        return True

    def release_all(self):
        """Queue a key up for every key Helix is holding down."""
        with self._lock:
            held, self._held = sorted(self._held), set()
        for usage in held:
            self._put(f"km.up({usage})", 0.0)

    def held(self):
        with self._lock:
            return set(self._held)

    def drain(self, timeout=1.0):
        """Wait until every queued command has been sent. True if that happened in time."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            with self._lock:
                if self._pending == 0:
                    return True
            time.sleep(0.005)
        return False

    def _put(self, cmd, wait_s):
        with self._lock:
            self._pending += 1
        self._q.put((cmd, wait_s))

    def _run(self):
        while True:
            cmd, wait_s = self._q.get()
            try:
                if not self._send(cmd):
                    print(f"[Keyboard] Not sent (MAKCU not connected?): {cmd}")
                if wait_s:
                    self._sleep(wait_s)
            except Exception as e:
                print(f"[Keyboard] {cmd} failed: {e}")
            finally:
                with self._lock:
                    self._pending -= 1
```

- [ ] **Step 5: Route `press_key` through the queue in `mouse/makcu.py`**

At the top, next to the existing `from mouse.keys import key_usage`, add:

```python
from mouse.keyboard import KeyboardQueue
```

Replace the whole existing `press_key` method (currently it ends with `return makcu_controller.send_text(f"km.press({usage},{CLICK_HOLD_MS})")`) with:

```python
    @staticmethod
    def press_key(key_name):
        """Tap a keyboard key (km.press, firmware-timed) through the shared keyboard
        queue, so it never overlaps another key command. Takes a name from mouse/keys.py."""
        if key_usage(key_name) is None or not makcu_controller.is_connected():
            return False
        return keyboard.tap(key_name, CLICK_HOLD_MS)
```

At the very end of `mouse/makcu.py` (after the `makcu_controller` class), add:

```python


# Every keyboard command goes through this one queue (see mouse/keyboard.py). The lambda
# looks send_text up at call time, so the controller can be swapped or stubbed.
keyboard = KeyboardQueue(lambda cmd: makcu_controller.send_text(cmd))
```

- [ ] **Step 6: Run the tests and confirm they pass**

Run: `cd /home/jason/Downloads/final/Helix && python3 -m pytest -q -s $S/tests/test_keyboard.py`
Expected: `9 passed`.

- [ ] **Step 7: Commit**

```bash
cd /home/jason/Downloads/final/Helix
git add mouse/keyboard.py mouse/makcu.py
git commit -m "feat: keyboard queue so key commands never overlap; Flashlight Key uses it

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
git fetch -q origin && git log --oneline HEAD..origin/main   # must print nothing
git push -q origin main
```

---

### Task 2: Hold Breath settings and API

**Files:**
- Modify: `state.py` (`__init__` after the Flashlight block ~line 46; after `get_pre_fire_delay` ~line 200; `to_dict` ~line 385; `from_dict` ~line 440)
- Create: `routers/holdbreath.py`
- Modify: `routers/streamdeck.py`, `routers/diagnostics.py`, `main.py`
- Test: `$S/tests/test_hold_breath_api.py`

**Interfaces:**
- Consumes: `mouse.keys.normalize_key`; `shared.state`, `shared.save_async`.
- Produces:
  - `AppState` attributes `hb_enabled`, `hb_trigger`, `hb_ads_mode`, `hb_breath_mode`, `hb_key`, `hb_tap_on_release`, `hb_delay_ms`, `hb_max_hold_ms`.
  - `AppState.get_hold_breath() -> dict` with keys `enabled, trigger, ads_mode, breath_mode, key, tap_on_release, delay_ms, max_hold_ms`; `AppState.toggle_hold_breath()`; `to_dict()["hold_breath"]` (same dict).
  - `POST /api/hold_breath` (partial update) → `{"ok": true}`; `POST /api/hold_breath/toggle` → `{"enabled": bool}`.
  - `main._ws_payload() -> dict` (the `/ws` message) with new keys `hold_breath_enabled`, `hold_breath_active`, `hold_breath_ads_mode`.
  - `/api/streamdeck` new keys `hold_breath` (bool, enabled and Recoil ON), `hold_breath_ads` (`hold`/`toggle`).
  - `/api/diagnostics` new key `hold_breath`.

- [ ] **Step 1: Write the failing tests**

`$S/tests/test_hold_breath_api.py`:

```python
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from state import AppState

DEFAULTS = {"enabled": False, "trigger": "RMB", "ads_mode": "hold", "breath_mode": "hold",
            "key": "NONE", "tap_on_release": False, "delay_ms": 0.0, "max_hold_ms": 0.0}


def test_defaults():
    assert AppState().get_hold_breath() == DEFAULTS


def test_round_trip():
    s = AppState()
    s.hb_enabled, s.hb_trigger, s.hb_ads_mode, s.hb_breath_mode = True, "M4", "toggle", "toggle"
    s.hb_key, s.hb_tap_on_release, s.hb_delay_ms, s.hb_max_hold_ms = "leftshift", True, 150.0, 3000.0
    d = s.to_dict()
    assert d["hold_breath"] == s.get_hold_breath()
    s2 = AppState()
    s2.from_dict(d)
    assert s2.get_hold_breath() == s.get_hold_breath()


def test_old_config_without_hold_breath():
    s = AppState()
    s.from_dict({"recoil": {"enabled": True}, "flashlight": {"key": "t"}})
    assert s.get_hold_breath() == DEFAULTS
    assert s.recoil_enabled is True and s.flashlight_key == "t"


def test_toggle():
    s = AppState()
    s.toggle_hold_breath()
    assert s.hb_enabled is True
    s.toggle_hold_breath()
    assert s.hb_enabled is False


@pytest.fixture
def client(monkeypatch):
    from routers import holdbreath as R

    async def no_save():
        pass

    monkeypatch.setattr(R, "save_async", no_save)
    fresh = AppState()
    monkeypatch.setattr(R, "state", fresh)
    app = FastAPI()
    app.include_router(R.router)
    return TestClient(app), fresh


def test_partial_updates(client):
    c, st = client
    assert c.post("/api/hold_breath", json={"ads_mode": "toggle"}).json() == {"ok": True}
    assert st.get_hold_breath() == {**DEFAULTS, "ads_mode": "toggle"}
    assert c.post("/api/hold_breath", json={"key": "Shift"}).status_code == 200
    assert st.hb_key == "leftshift"
    assert c.post("/api/hold_breath", json={"trigger": "m5", "delay_ms": 150,
                                            "max_hold_ms": 3000, "tap_on_release": True,
                                            "breath_mode": "toggle", "enabled": True}).status_code == 200
    assert st.get_hold_breath() == {"enabled": True, "trigger": "M5", "ads_mode": "toggle",
                                    "breath_mode": "toggle", "key": "leftshift",
                                    "tap_on_release": True, "delay_ms": 150.0, "max_hold_ms": 3000.0}
    assert c.post("/api/hold_breath", json={"key": "NONE"}).status_code == 200
    assert st.hb_key == "NONE"
    assert c.post("/api/hold_breath", json={"delay_ms": 0, "max_hold_ms": 0}).status_code == 200
    assert st.hb_delay_ms == 0.0 and st.hb_max_hold_ms == 0.0
    assert c.post("/api/hold_breath", json={"delay_ms": 2000, "max_hold_ms": 30000}).status_code == 200


@pytest.mark.parametrize("body", [
    {"trigger": "LMB"}, {"trigger": "X"}, {"ads_mode": "hold2"}, {"breath_mode": ""},
    {"key": "foo"}, {"delay_ms": -1}, {"delay_ms": 2001}, {"max_hold_ms": -5},
    {"max_hold_ms": 30001}, {"ads_mode": "toggle", "delay_ms": 5000},
    {"key": "f", "trigger": "LMB"},
])
def test_invalid_update_changes_nothing(client, body):
    c, st = client
    before = st.get_hold_breath()
    r = c.post("/api/hold_breath", json=body)
    assert r.status_code == 400, r.text
    assert r.json()["detail"]
    assert st.get_hold_breath() == before


def test_toggle_endpoint(client):
    c, st = client
    assert c.post("/api/hold_breath/toggle").json() == {"enabled": True}
    assert c.post("/api/hold_breath/toggle").json() == {"enabled": False}


def test_streamdeck_keys(monkeypatch):
    from routers import streamdeck as SD
    s = AppState()
    s.recoil_enabled, s.hb_enabled, s.hb_ads_mode = True, True, "toggle"
    monkeypatch.setattr(SD, "state", s)
    app = FastAPI()
    app.include_router(SD.router)
    d = TestClient(app).get("/api/streamdeck").json()
    assert d["hold_breath"] is True and d["hold_breath_ads"] == "toggle"
    assert {"recoil", "flashlight", "makcu", "script"} <= set(d)   # existing keys unchanged
    s.recoil_enabled = False
    assert TestClient(app).get("/api/streamdeck").json()["hold_breath"] is False


def test_ws_payload(monkeypatch):
    import main
    s = main.state
    monkeypatch.setattr(s, "recoil_enabled", True)
    monkeypatch.setattr(s, "hb_enabled", True)
    monkeypatch.setattr(s, "hb_ads_mode", "toggle")
    p = main._ws_payload()
    assert p["hold_breath_enabled"] is True
    assert p["hold_breath_active"] is True
    assert p["hold_breath_ads_mode"] == "toggle"
    for k in ("makcu_connected", "recoil_enabled", "flashlight_enabled", "flashlight_active",
              "loaded_script", "theme", "burst_history", "script_sensitivity"):
        assert k in p                                                   # existing keys kept
    monkeypatch.setattr(s, "recoil_enabled", False)
    assert main._ws_payload()["hold_breath_active"] is False
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `cd /home/jason/Downloads/final/Helix && python3 -m pytest -q -s $S/tests/test_hold_breath_api.py`
Expected: failures with `AttributeError: 'AppState' object has no attribute 'get_hold_breath'` and `ImportError` for `routers.holdbreath`.

- [ ] **Step 3: Add the settings to `state.py`**

In `__init__`, directly after the Flashlight block (after the line `self.pre_fire_max_ms: float = 180.0`), add:

```python

        # ── Hold Breath ───────────────────────────────────────────────────────
        self.hb_enabled = False
        self.hb_trigger = "RMB"             # aim button: RMB | MMB | M4 | M5
        self.hb_ads_mode = "hold"           # hold | toggle (how the game aims)
        self.hb_breath_mode = "hold"        # hold | toggle (how the game's hold breath works)
        self.hb_key = "NONE"                # key name from mouse/keys.py, or NONE
        self.hb_tap_on_release = False      # toggle breath: tap again when aiming ends
        self.hb_delay_ms: float = 0.0       # wait after aiming starts (scope-in)
        self.hb_max_hold_ms: float = 0.0    # stop after this long; 0 = no limit
```

Directly after the method `get_pre_fire_delay` (after its line `return random.uniform(lo, hi) / 1000.0`), add:

```python

    # ── Hold Breath interface ─────────────────────────────────────────────────

    def toggle_hold_breath(self):
        with self._lock:
            self.hb_enabled = not self.hb_enabled

    def get_hold_breath(self) -> dict:
        with self._lock:
            return self._hold_breath_dict()

    def _hold_breath_dict(self) -> dict:
        # Caller holds self._lock.
        return {
            "enabled": self.hb_enabled,
            "trigger": self.hb_trigger,
            "ads_mode": self.hb_ads_mode,
            "breath_mode": self.hb_breath_mode,
            "key": self.hb_key,
            "tap_on_release": self.hb_tap_on_release,
            "delay_ms": self.hb_delay_ms,
            "max_hold_ms": self.hb_max_hold_ms,
        }
```

In `to_dict`, after the `"flashlight": {...},` entry (its last line is `"pre_fire_max_ms": self.pre_fire_max_ms,` followed by `},`), add:

```python
                "hold_breath": self._hold_breath_dict(),
```

In `from_dict`, inside the second `with self._lock:` block, directly after the line `self.pre_fire_max_ms    = float(fl.get("pre_fire_max_ms", 15.0))`, add:

```python

            hb = data.get("hold_breath", {})
            self.hb_enabled        = bool(hb.get("enabled", False))
            self.hb_trigger        = hb.get("trigger", "RMB")
            self.hb_ads_mode       = hb.get("ads_mode", "hold")
            self.hb_breath_mode    = hb.get("breath_mode", "hold")
            self.hb_key            = hb.get("key", "NONE")
            self.hb_tap_on_release = bool(hb.get("tap_on_release", False))
            self.hb_delay_ms       = float(hb.get("delay_ms", 0.0))
            self.hb_max_hold_ms    = float(hb.get("max_hold_ms", 0.0))
```

- [ ] **Step 4: Create `routers/holdbreath.py`**

```python
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from mouse.keys import normalize_key
from shared import state, save_async

router = APIRouter(prefix="/api/hold_breath", tags=["hold_breath"])

TRIGGERS = ("RMB", "MMB", "M4", "M5")   # LMB fires, so it cannot be the aim button
MODES = ("hold", "toggle")
MAX_DELAY_MS = 2000
MAX_HOLD_MS = 30000


class HoldBreathUpdate(BaseModel):
    enabled:        Optional[bool]  = None
    trigger:        Optional[str]   = None
    ads_mode:       Optional[str]   = None
    breath_mode:    Optional[str]   = None
    key:            Optional[str]   = None   # key name from mouse/keys.py, or NONE
    tap_on_release: Optional[bool]  = None
    delay_ms:       Optional[float] = None
    max_hold_ms:    Optional[float] = None


def _mode(value, field):
    if value is None:
        return None
    v = value.strip().lower()
    if v not in MODES:
        raise HTTPException(400, f"{field} must be hold or toggle")
    return v


@router.post("/toggle")
async def toggle_hold_breath():
    state.toggle_hold_breath()
    await save_async()
    return {"enabled": state.get_hold_breath()["enabled"]}


@router.post("")
async def update_hold_breath(u: HoldBreathUpdate):
    # Validate everything first, so a bad field never leaves a half-applied update.
    trigger = None
    if u.trigger is not None:
        trigger = u.trigger.strip().upper()
        if trigger not in TRIGGERS:
            raise HTTPException(400, f"trigger must be one of {', '.join(TRIGGERS)}")
    ads = _mode(u.ads_mode, "ads_mode")
    breath = _mode(u.breath_mode, "breath_mode")
    key = None
    if u.key is not None:
        key = "NONE" if u.key.strip().upper() in ("", "NONE") else normalize_key(u.key)
        if key is None:
            raise HTTPException(400, f"Unknown key: {u.key}")
    if u.delay_ms is not None and not 0 <= u.delay_ms <= MAX_DELAY_MS:
        raise HTTPException(400, f"delay_ms must be 0-{MAX_DELAY_MS}")
    if u.max_hold_ms is not None and not 0 <= u.max_hold_ms <= MAX_HOLD_MS:
        raise HTTPException(400, f"max_hold_ms must be 0-{MAX_HOLD_MS} (0 = no limit)")

    with state._lock:
        if u.enabled        is not None: state.hb_enabled        = u.enabled
        if trigger          is not None: state.hb_trigger        = trigger
        if ads              is not None: state.hb_ads_mode       = ads
        if breath           is not None: state.hb_breath_mode    = breath
        if key              is not None: state.hb_key            = key
        if u.tap_on_release is not None: state.hb_tap_on_release = u.tap_on_release
        if u.delay_ms       is not None: state.hb_delay_ms       = float(u.delay_ms)
        if u.max_hold_ms    is not None: state.hb_max_hold_ms    = float(u.max_hold_ms)
    await save_async()
    return {"ok": True}
```

- [ ] **Step 5: Expose the new keys**

`routers/streamdeck.py`: in `streamdeck_state()`, add two entries to the `content` dict after `"script": state.loaded_script,`:

```python
            "hold_breath": state.hb_enabled and state.recoil_enabled,
            "hold_breath_ads": state.hb_ads_mode,
```

`routers/diagnostics.py`: in `diagnostics()`, after the line `"flashlight": cfg["flashlight"],` add:

```python
        "hold_breath": cfg["hold_breath"],
```

`main.py`:
1. Change `from routers import recoil, scripts, flashlight, settings, cs2, streamdeck, device` to `from routers import recoil, scripts, flashlight, settings, cs2, streamdeck, device, holdbreath`.
2. After `app.include_router(flashlight.router)` add `app.include_router(holdbreath.router)`.
3. Move the `/ws` message into a function. In `_broadcast_loop`, replace everything from `snapshot = state.to_dict()` through the closing `})` of `msg = json.dumps({ ... })` with the single line `msg = json.dumps(_ws_payload())`, keeping the indentation and the hash/send code after it unchanged. Add this function directly above `async def _broadcast_loop():`. It must contain every key the old inline dict had, in the same order, plus the three new ones:

```python
def _ws_payload() -> dict:
    """The /ws status message (pushed only when its hash changes)."""
    snapshot = state.to_dict()
    r = snapshot["recoil"]
    fl = snapshot["flashlight"]
    s = snapshot["settings"]
    hb = snapshot["hold_breath"]
    return {
        "makcu_connected":          makcu_controller.is_connected(),
        "recoil_enabled":           r["enabled"],
        "flashlight_enabled":       fl["enabled"],
        "flashlight_active":        fl["enabled"] and r["enabled"],
        "loaded_script":            r["loaded_script"],
        "lmb_pressed":              makcu_controller.get_button_state("LMB"),
        "recoil_scalar":            r["recoil_scalar"],
        "x_control":                r["x_control"],
        "y_control":                r["y_control"],
        "randomisation_strength":   r["randomisation_strength"],
        "return_speed":             r["return_speed"],
        "randomisation":            r["randomisation"],
        "return_crosshair":         r["return_crosshair"],
        "require_aim":              r["require_aim"],
        "loop_recoil":              r["loop_recoil"],
        "toggle_keybind":           r["toggle_keybind"],
        "cycle_keybind":            r["cycle_keybind"],
        "theme":                    s["theme"],
        "burst_history":            state.get_burst_history(),
        "cs2_weapon":               s["cs2_weapon"],
        "script_sensitivity":       r.get("script_sensitivity", 1.0),
        "hold_breath_enabled":      hb["enabled"],
        "hold_breath_active":       hb["enabled"] and r["enabled"],
        "hold_breath_ads_mode":     hb["ads_mode"],
    }
```

Before replacing, open `main.py` and compare: if the old inline dict has any key not listed above, add it to `_ws_payload()` too.

- [ ] **Step 6: Run the tests and confirm they pass**

Run: `cd /home/jason/Downloads/final/Helix && python3 -m pytest -q -s $S/tests`
Expected: `28 passed` (9 from Task 1, 19 here).

- [ ] **Step 7: Restart the server and check live (read-only)**

```bash
curl -s -X POST localhost:8000/api/server/restart; echo
for i in $(seq 1 30); do sleep 1; curl -sf localhost:8000/api/device >/dev/null && break; done
curl -s localhost:8000/api/state | python3 -c "import json,sys;print(json.load(sys.stdin)['hold_breath'])"
curl -s localhost:8000/api/streamdeck; echo
curl -s -o /dev/null -w '%{http_code}\n' -X POST localhost:8000/api/hold_breath -H 'Content-Type: application/json' -d '{"trigger":"LMB"}'
journalctl -u helix --since "-1min" --no-pager | grep -iE "error|traceback" || echo "log clean"
```

Expected: the `hold_breath` dict with the defaults (or the user's values if already set); `/api/streamdeck` includes `"hold_breath"` and `"hold_breath_ads"`; the invalid POST prints `400`; "log clean".

- [ ] **Step 8: Commit**

```bash
cd /home/jason/Downloads/final/Helix
git add state.py routers/holdbreath.py routers/streamdeck.py routers/diagnostics.py main.py
git commit -m "feat: Hold Breath settings and API (additive: /api/hold_breath, /ws, /api/streamdeck)

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
git fetch -q origin && git log --oneline HEAD..origin/main   # must print nothing
git push -q origin main
```

---

### Task 3: Hold Breath state machine

**Files:**
- Create: `features/holdbreath/__init__.py` (empty), `features/holdbreath/machine.py`
- Test: `$S/tests/test_hold_breath_machine.py`

**Interfaces:**
- Consumes: nothing (pure logic, no imports from Helix).
- Produces:
  - `HoldBreathConfig` (frozen dataclass): `trigger: str = "RMB"`, `ads_mode: str = "hold"`, `breath_mode: str = "hold"`, `key: str = "NONE"`, `tap_on_release: bool = False`, `delay_ms: float = 0.0`, `max_hold_ms: float = 0.0`; `HoldBreathConfig.from_settings(d: dict)` takes the dict from `AppState.get_hold_breath()` (it ignores `enabled`).
  - `HoldBreathMachine()` with `reset()` and `step(now: float, trigger_down: bool, active: bool, cfg: HoldBreathConfig) -> list[tuple[str, str]]`. `now` is in seconds (monotonic). Each action is `(op, key)` with `op` in `"down" | "up" | "tap"`.
  - Attributes `phase` (`"idle" | "waiting" | "breathing" | "spent"`) and `aiming` (bool), for tests and logs.

Behaviour (copied from the spec's table):

| From | Event | To | Key action |
|---|---|---|---|
| IDLE | aiming starts | WAITING | none |
| WAITING | aiming ends | IDLE | none |
| WAITING | delay elapsed | BREATHING | hold: down. toggle: tap |
| BREATHING | max hold elapsed (if > 0) | SPENT | hold: up. toggle: tap |
| BREATHING | aiming ends | IDLE | hold: up. toggle: tap if `tap_on_release` |
| SPENT | aiming ends | IDLE | none |
| any | inactive, or `key`/`breath_mode`/`trigger`/`ads_mode` changes | IDLE | if BREATHING: as for "aiming ends", with the old settings |

Aiming: `ads_mode = hold` → aiming while the trigger is down. `ads_mode = toggle` → each press (up→down edge) flips aiming. Aiming resets to false when inactive or when `trigger`/`ads_mode` (or `key`/`breath_mode`) change; a button already held at that moment does not count as a new press. Changing `delay_ms`, `max_hold_ms` or `tap_on_release` does not interrupt anything; the new values apply from the next step.

- [ ] **Step 1: Write the failing tests**

`$S/tests/test_hold_breath_machine.py`:

```python
from features.holdbreath.machine import HoldBreathConfig, HoldBreathMachine

LS = "leftshift"
BASE = HoldBreathConfig(key=LS)


def run(events, cfg=BASE):
    """events: (t_ms, trigger_down, active[, cfg]). Returns [(t_ms, op, key)]."""
    m = HoldBreathMachine()
    out = []
    for ev in events:
        t, trig, act = ev[:3]
        c = ev[3] if len(ev) > 3 else cfg
        out += [(t, op, k) for op, k in m.step(t / 1000.0, trig, act, c)]
    return out


T, F = True, False


def test_hold_ads_hold_breath():
    assert run([(0, F, T), (10, T, T), (20, T, T), (500, F, T), (510, F, T)]) == \
        [(10, "down", LS), (500, "up", LS)]


def test_delay():
    c = HoldBreathConfig(key=LS, delay_ms=150)
    assert run([(0, T, T), (100, T, T), (149, T, T), (150, T, T), (400, F, T)], c) == \
        [(150, "down", LS), (400, "up", LS)]


def test_release_before_delay_does_nothing():
    c = HoldBreathConfig(key=LS, delay_ms=150)
    assert run([(0, T, T), (100, F, T), (200, F, T)], c) == []


def test_max_hold_stops_and_stays_stopped_until_next_aim():
    c = HoldBreathConfig(key=LS, max_hold_ms=1000)
    assert run([(0, T, T), (999, T, T), (1000, T, T), (1500, T, T), (1600, F, T), (2000, T, T)], c) == \
        [(0, "down", LS), (1000, "up", LS), (2000, "down", LS)]


def test_toggle_breath_without_tap_on_release():
    c = HoldBreathConfig(key=LS, breath_mode="toggle")
    assert run([(0, T, T), (500, F, T)], c) == [(0, "tap", LS)]


def test_toggle_breath_with_tap_on_release():
    c = HoldBreathConfig(key=LS, breath_mode="toggle", tap_on_release=True)
    assert run([(0, T, T), (500, F, T)], c) == [(0, "tap", LS), (500, "tap", LS)]


def test_toggle_breath_max_hold_then_release_taps_once_only():
    c = HoldBreathConfig(key=LS, breath_mode="toggle", tap_on_release=True, max_hold_ms=300)
    assert run([(0, T, T), (300, T, T), (600, F, T)], c) == [(0, "tap", LS), (300, "tap", LS)]


def test_toggle_ads_click_in_click_out():
    c = HoldBreathConfig(key=LS, ads_mode="toggle")
    assert run([(0, T, T), (50, F, T), (1000, F, T), (2000, T, T), (2050, F, T), (3000, T, T)], c) == \
        [(0, "down", LS), (2000, "up", LS), (3000, "down", LS)]


def test_inactive_mid_breath_releases_then_resumes_if_still_holding():
    assert run([(0, T, T), (300, T, F), (400, T, T)]) == \
        [(0, "down", LS), (300, "up", LS), (400, "down", LS)]


def test_inactive_mid_breath_toggle_ads_resets_aim():
    c = HoldBreathConfig(key=LS, ads_mode="toggle")
    assert run([(0, T, T), (50, F, T), (300, F, F), (400, F, T), (500, T, T)], c) == \
        [(0, "down", LS), (300, "up", LS), (500, "down", LS)]


def test_inactive_toggle_ads_held_button_is_not_a_new_press():
    c = HoldBreathConfig(key=LS, ads_mode="toggle")
    assert run([(0, T, T), (100, T, F), (200, T, T), (300, F, T), (400, T, T)], c) == \
        [(0, "down", LS), (100, "up", LS), (400, "down", LS)]


def test_inactive_toggle_breath_taps_only_with_tap_on_release():
    c = HoldBreathConfig(key=LS, breath_mode="toggle")
    assert run([(0, T, T), (300, T, F)], c) == [(0, "tap", LS)]
    c2 = HoldBreathConfig(key=LS, breath_mode="toggle", tap_on_release=True)
    assert run([(0, T, T), (300, T, F)], c2) == [(0, "tap", LS), (300, "tap", LS)]


def test_inactive_while_waiting_or_spent_sends_nothing():
    c = HoldBreathConfig(key=LS, delay_ms=500)
    assert run([(0, T, T), (100, T, F)], c) == []
    c2 = HoldBreathConfig(key=LS, max_hold_ms=100)
    assert run([(0, T, T), (100, T, T), (200, T, F)], c2) == [(0, "down", LS), (100, "up", LS)]


def test_key_change_mid_breath_releases_old_key_hold_ads_restarts():
    c2 = HoldBreathConfig(key="f")
    assert run([(0, T, T, BASE), (300, T, T, c2), (600, F, T, c2)]) == \
        [(0, "down", LS), (300, "up", LS), (300, "down", "f"), (600, "up", "f")]


def test_key_change_mid_breath_toggle_ads_does_not_restart():
    c1 = HoldBreathConfig(key=LS, ads_mode="toggle")
    c2 = HoldBreathConfig(key="f", ads_mode="toggle")
    assert run([(0, T, T, c1), (50, F, T, c1), (300, F, T, c2), (600, F, T, c2)]) == \
        [(0, "down", LS), (300, "up", LS)]


def test_breath_mode_change_mid_breath_ends_with_old_mode():
    c2 = HoldBreathConfig(key=LS, breath_mode="toggle")
    assert run([(0, T, T, BASE), (300, T, T, c2)]) == \
        [(0, "down", LS), (300, "up", LS), (300, "tap", LS)]


def test_trigger_change_mid_breath_releases():
    c2 = HoldBreathConfig(key=LS, trigger="MMB")
    assert run([(0, T, T, BASE), (300, F, T, c2)]) == [(0, "down", LS), (300, "up", LS)]


def test_timing_changes_do_not_interrupt():
    c_delay = HoldBreathConfig(key=LS, delay_ms=500)
    c_tap = HoldBreathConfig(key=LS, delay_ms=500, tap_on_release=True)
    c_max = HoldBreathConfig(key=LS, delay_ms=500, tap_on_release=True, max_hold_ms=200)
    assert run([(0, T, T, BASE), (300, T, T, c_delay), (400, T, T, c_tap), (600, T, T, c_max)]) == \
        [(0, "down", LS), (600, "up", LS)]


def test_reset():
    m = HoldBreathMachine()
    assert m.step(0.0, True, True, BASE) == [("down", LS)]
    m.reset()
    assert (m.phase, m.aiming) == ("idle", False)


def test_from_settings():
    d = {"enabled": True, "trigger": "M4", "ads_mode": "toggle", "breath_mode": "toggle",
         "key": LS, "tap_on_release": True, "delay_ms": 150, "max_hold_ms": 3000}
    assert HoldBreathConfig.from_settings(d) == HoldBreathConfig(
        trigger="M4", ads_mode="toggle", breath_mode="toggle", key=LS,
        tap_on_release=True, delay_ms=150.0, max_hold_ms=3000.0)
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `cd /home/jason/Downloads/final/Helix && python3 -m pytest -q -s $S/tests/test_hold_breath_machine.py`
Expected: `ModuleNotFoundError: No module named 'features.holdbreath'`.

- [ ] **Step 3: Implement**

Create an empty `features/holdbreath/__init__.py`. Create `features/holdbreath/machine.py`:

```python
"""Hold Breath state machine: pure logic, no I/O, no threads.

The loop (holdbreath.py) calls step() every few ms with the aim button state, whether
Hold Breath is active, and a settings snapshot; step() returns the key actions to send.
See docs/superpowers/specs/2026-10-09-hold-breath-design.md for the state table."""
from dataclasses import dataclass

IDLE, WAITING, BREATHING, SPENT = "idle", "waiting", "breathing", "spent"


@dataclass(frozen=True)
class HoldBreathConfig:
    trigger: str = "RMB"
    ads_mode: str = "hold"         # hold | toggle
    breath_mode: str = "hold"      # hold | toggle
    key: str = "NONE"
    tap_on_release: bool = False
    delay_ms: float = 0.0
    max_hold_ms: float = 0.0       # 0 = no limit

    @classmethod
    def from_settings(cls, d):
        return cls(
            trigger=d["trigger"], ads_mode=d["ads_mode"], breath_mode=d["breath_mode"],
            key=d["key"], tap_on_release=bool(d["tap_on_release"]),
            delay_ms=float(d["delay_ms"]), max_hold_ms=float(d["max_hold_ms"]),
        )

    def identity(self):
        """Settings whose change ends a breath in progress and resets aiming."""
        return (self.key, self.breath_mode, self.trigger, self.ads_mode)


class HoldBreathMachine:
    def __init__(self):
        self.reset()

    def reset(self):
        self.phase = IDLE
        self.aiming = False
        self._prev_trigger = False
        self._t_aim = 0.0
        self._t_breath = 0.0
        self._cfg = None

    def step(self, now, trigger_down, active, cfg):
        actions = []
        prev = self._cfg
        if prev is not None and prev.identity() != cfg.identity():
            actions += self._stop(prev)          # release with the settings it started with
            self._idle(trigger_down)
        self._cfg = cfg

        if not active:
            actions += self._stop(cfg)
            self._idle(trigger_down)
            return actions

        pressed = trigger_down and not self._prev_trigger
        self._prev_trigger = trigger_down
        if cfg.ads_mode == "toggle":
            if pressed:
                self.aiming = not self.aiming
        else:
            self.aiming = trigger_down

        if self.phase == IDLE and self.aiming:
            self.phase, self._t_aim = WAITING, now

        if self.phase == WAITING:
            if not self.aiming:
                self.phase = IDLE
            elif (now - self._t_aim) * 1000.0 >= cfg.delay_ms:
                actions.append(("down" if cfg.breath_mode == "hold" else "tap", cfg.key))
                self.phase, self._t_breath = BREATHING, now
        elif self.phase == BREATHING:
            if not self.aiming:
                actions += self._stop(cfg)
                self.phase = IDLE
            elif cfg.max_hold_ms > 0 and (now - self._t_breath) * 1000.0 >= cfg.max_hold_ms:
                actions.append(("up" if cfg.breath_mode == "hold" else "tap", cfg.key))
                self.phase = SPENT
        elif self.phase == SPENT and not self.aiming:
            self.phase = IDLE
        return actions

    def _stop(self, cfg):
        """Actions that end a breath in progress (none unless BREATHING)."""
        if self.phase != BREATHING:
            return []
        if cfg.breath_mode == "hold":
            return [("up", cfg.key)]
        return [("tap", cfg.key)] if cfg.tap_on_release else []

    def _idle(self, trigger_down):
        self.phase = IDLE
        self.aiming = False
        self._prev_trigger = trigger_down     # a button already held is not a new press
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `cd /home/jason/Downloads/final/Helix && python3 -m pytest -q -s $S/tests/test_hold_breath_machine.py`
Expected: `20 passed`. If one fails, fix the machine, not the expected values; the expected values come from the spec's table. If a test seems to contradict the table, stop and ask the user.

- [ ] **Step 5: Commit**

```bash
cd /home/jason/Downloads/final/Helix
git add features/holdbreath/__init__.py features/holdbreath/machine.py
git commit -m "feat: Hold Breath state machine (hold/toggle ADS, hold/toggle breath, delay, max hold)

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
git fetch -q origin && git log --oneline HEAD..origin/main   # must print nothing
git push -q origin main
```

---

### Task 4: Hold Breath loop, startup and shutdown

**Files:**
- Create: `features/holdbreath/holdbreath.py`
- Modify: `main.py` (imports; lifespan start; lifespan shutdown)
- Test: `$S/tests/test_hold_breath_loop.py`

**Interfaces:**
- Consumes: `HoldBreathConfig`, `HoldBreathMachine` (Task 3); `mouse.makcu.keyboard` with `down/up/tap/release_all` (Task 1); `AppState.get_hold_breath()`, `AppState.get_is_enabled()` (Task 2; `get_is_enabled` is the Recoil switch); `makcu_controller.get_button_state(name)`, `makcu_controller.connection_lock`, `.controller`, `.is_connected_flag`.
- Produces: `run_hold_breath(state, kb=None, stop=None, clock=time.monotonic, sleep=time.sleep)`, which loops until `stop` (a `threading.Event`) is set. In production it is called with `(state,)` only.

- [ ] **Step 1: Write the failing tests**

`$S/tests/test_hold_breath_loop.py`:

```python
import threading
import time

import pytest

from mouse.makcu import makcu_controller
from state import AppState
import features.holdbreath.holdbreath as HB


class FakeKB:
    def __init__(self):
        self.calls = []
        self.lock = threading.Lock()

    def _rec(self, op, key):
        with self.lock:
            self.calls.append((op, key))
        return True

    def down(self, key): return self._rec("down", key)
    def up(self, key): return self._rec("up", key)
    def tap(self, key, hold_ms=30): return self._rec("tap", key)
    def release_all(self): self._rec("release_all", None)

    def snapshot(self):
        with self.lock:
            return list(self.calls)


@pytest.fixture
def rig(monkeypatch):
    buttons = {"LMB": False, "RMB": False, "MMB": False, "M4": False, "M5": False}
    monkeypatch.setattr(makcu_controller, "get_button_state", lambda n: buttons.get(n, False))
    monkeypatch.setattr(makcu_controller, "controller", object())
    monkeypatch.setattr(makcu_controller, "is_connected_flag", True)
    st = AppState()
    st.recoil_enabled, st.hb_enabled, st.hb_key = True, True, "leftshift"
    kb, stop = FakeKB(), threading.Event()
    t = threading.Thread(target=HB.run_hold_breath, args=(st,), kwargs={"kb": kb, "stop": stop},
                         daemon=True)
    t.start()
    time.sleep(0.05)
    yield st, buttons, kb
    stop.set()
    t.join(1)


def settle():
    time.sleep(0.06)


def test_connect_and_reconnect_release_the_key(rig, monkeypatch):
    st, buttons, kb = rig
    assert kb.snapshot() == [("up", "leftshift")]                   # first connect
    monkeypatch.setattr(makcu_controller, "controller", object())    # reconnect
    settle()
    assert kb.snapshot() == [("up", "leftshift"), ("up", "leftshift")]


def test_aim_in_and_out(rig):
    st, buttons, kb = rig
    buttons["RMB"] = True; settle()
    buttons["RMB"] = False; settle()
    assert kb.snapshot()[1:] == [("down", "leftshift"), ("up", "leftshift")]


def test_recoil_off_mid_aim_releases(rig):
    st, buttons, kb = rig
    buttons["RMB"] = True; settle()
    st.recoil_enabled = False; settle()
    assert kb.snapshot()[1:] == [("down", "leftshift"), ("up", "leftshift")]


def test_disabled_does_nothing(rig):
    st, buttons, kb = rig
    st.hb_enabled = False
    buttons["RMB"] = True; settle()
    assert kb.snapshot()[1:] == []


def test_no_key_does_nothing(rig):
    st, buttons, kb = rig
    st.hb_key = "NONE"
    buttons["RMB"] = True; settle()
    assert kb.snapshot()[1:] == []


def test_selected_trigger_only(rig):
    st, buttons, kb = rig
    st.hb_trigger = "M4"
    buttons["RMB"] = True; settle()
    assert kb.snapshot()[1:] == []
    buttons["M4"] = True; settle()
    assert kb.snapshot()[1:] == [("down", "leftshift")]


def test_disconnect_mid_aim_releases(rig, monkeypatch):
    st, buttons, kb = rig
    buttons["RMB"] = True; settle()
    monkeypatch.setattr(makcu_controller, "is_connected_flag", False)
    settle()
    assert kb.snapshot()[1:] == [("down", "leftshift"), ("up", "leftshift")]


def test_toggle_breath_taps(rig):
    st, buttons, kb = rig
    st.hb_breath_mode, st.hb_tap_on_release = "toggle", True
    buttons["RMB"] = True; settle()
    buttons["RMB"] = False; settle()
    assert kb.snapshot()[1:] == [("tap", "leftshift"), ("tap", "leftshift")]
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `cd /home/jason/Downloads/final/Helix && python3 -m pytest -q -s $S/tests/test_hold_breath_loop.py`
Expected: `ModuleNotFoundError: No module named 'features.holdbreath.holdbreath'`.

- [ ] **Step 3: Implement `features/holdbreath/holdbreath.py`**

```python
"""Hold Breath loop: watches the aim button and drives HoldBreathMachine.

Started by main.py's lifespan next to the Recoil and Flashlight loops. Every key action
goes through the shared keyboard queue (mouse/keyboard.py), so it never overlaps a
Flashlight Key tap."""
import time

from features.holdbreath.machine import HoldBreathConfig, HoldBreathMachine
from mouse.makcu import makcu_controller, keyboard as default_keyboard

POLL_S = 0.005


def _controller():
    """The live controller object, or None while disconnected."""
    with makcu_controller.connection_lock:
        return makcu_controller.controller if makcu_controller.is_connected_flag else None


def run_hold_breath(state, kb=None, stop=None, clock=time.monotonic, sleep=time.sleep):
    kb = kb or default_keyboard
    machine = HoldBreathMachine()
    last_ctrl = None
    while stop is None or not stop.is_set():
        try:
            settings = state.get_hold_breath()
            cfg = HoldBreathConfig.from_settings(settings)
            ctrl = _controller()
            if ctrl is not None and ctrl is not last_ctrl:
                # First connect or a reconnect: a key may still be down on the gaming PC
                # from before (crash, kill, dropped link). Release it and start clean.
                if cfg.key != "NONE":
                    kb.up(cfg.key)
                machine.reset()
            last_ctrl = ctrl
            active = (settings["enabled"] and state.get_is_enabled()
                      and cfg.key != "NONE" and ctrl is not None)
            trigger_down = makcu_controller.get_button_state(cfg.trigger)
            for op, key in machine.step(clock(), trigger_down, active, cfg):
                getattr(kb, op)(key)              # "down" | "up" | "tap"
                print(f"[HoldBreath] {op} {key}")
        except Exception as e:
            print(f"[HoldBreath] Unexpected error — releasing keys, thread continues: {e}")
            kb.release_all()
            machine.reset()
        sleep(POLL_S)
```

- [ ] **Step 4: Wire it into `main.py`**

1. Imports: after the line `from features.flashlight.flashlight import flashlight as flashlight_feature, shutdown_executor as _shutdown_flashlight_executor` add:

```python
from features.holdbreath.holdbreath import run_hold_breath
from mouse.makcu import keyboard
```

2. In `lifespan`, after the line that starts the flashlight thread (`threading.Thread(target=flashlight_feature.run_flashlight, args=(state,),     daemon=True).start()`), add:

```python
    threading.Thread(target=run_hold_breath, args=(state,), daemon=True, name="hold-breath").start()
```

3. In `lifespan`, after `yield` and `_shutdown_flashlight_executor()`, and before `makcu_controller.disconnect()`, add:

```python
    keyboard.release_all()     # never leave a key held down on the gaming PC
    keyboard.drain(1.0)
```

- [ ] **Step 5: Run all host tests**

Run: `cd /home/jason/Downloads/final/Helix && python3 -m pytest -q -s $S/tests`
Expected: `56 passed` (the loop tests print `[HoldBreath] ...` and one `[Keyboard] km.down(9) failed: boom` line; both are expected).

- [ ] **Step 6: Restart and check live (read-only)**

```bash
curl -s -X POST localhost:8000/api/server/restart; echo
for i in $(seq 1 30); do sleep 1; curl -sf localhost:8000/api/device >/dev/null && break; done
sleep 2
journalctl -u helix --since "-1min" --no-pager | grep -E "HoldBreath|Keyboard|Traceback|rror" || echo "no hold-breath output (expected while disabled)"
curl -s localhost:8000/api/device; echo
```

Expected: MAKCU connected, no `Unexpected error` or traceback. If the user has a key bound, one `[Keyboard]`-free startup is normal; the connect release is silent (no print).

- [ ] **Step 7: Commit**

```bash
cd /home/jason/Downloads/final/Helix
git add features/holdbreath/holdbreath.py main.py
git commit -m "feat: Hold Breath loop; release held keys on connect, reconnect and shutdown

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
git fetch -q origin && git log --oneline HEAD..origin/main   # must print nothing
git push -q origin main
```

---

### Task 5: Web UI: Hold Breath tab, header card, shared key binding

**Files:**
- Modify: `static/index.html` (CSS `#sp` ~line 45; tab bar ~line 447; header `#sp` markup ~line 440; new panel after the Flashlight panel ~line 556; `applyStatus` ~line 885; `loadState` ~line 952; `toggleFlashlight` ~line 1658; the Flashlight Key binding block starting at the comment `// ── Flashlight Key: click the box` ~line 1670; `pollMakcu` ~line 1940)
- Test: `$S/ui/ui_run.py`, `$S/ui/ui_shot.py`, `$S/ui/hb_ui_test.js`

**Interfaces:**
- Consumes: `GET /api/state` → `hold_breath` dict; `POST /api/hold_breath` (partial); `POST /api/hold_breath/toggle` → `{enabled}`; `/ws` keys `hold_breath_enabled`, `hold_breath_active`, `hold_breath_ads_mode`; `/api/streamdeck` key `hold_breath`. Existing page helpers: `$(id)`, `api(url, opts)` (throws `Error(responseText)` when not ok), `recErr(e)` (extracts `detail`), `notify(msg)`, `chk(id,v)`, `num(id,v)`, `sel(id,v)` (matches option value or text), `fv(el)`, `card(id, 'on'|'')`, `st(tab)`, `p(url, body)`.
- Produces: element ids `tab-holdbreath`, `hb-en`, `hb-trig`, `hb-ads`, `hb-bm`, `hb-tap-row`, `hb-tap`, `hb-key`, `hb-key-clear`, `hb-delay`, `hb-max`, `sc-hb`, `sc-hb-v`, `sc-hb-master`; functions `keyBinder(inputId, url)`, `hbSet(body)`, `hbApply(h)`, `hbLoad()`, `hbShowTap()`, `toggleHoldBreath()`. The existing `flKeyShow(k)` and `flKeySet(k)` keep working (now thin wrappers).

- [ ] **Step 1: Create the browser test tools**

`$S/ui/ui_run.py` runs a JS test in headless Chromium against the live page. The JS must resolve to a JSON list of `[name, ok, detail]`; stubbing is up to the JS. `--url` loads another page; `--prepend FILE` evaluates FILE's source first (used for the Stream Deck plugin).

```python
"""Usage: python3 ui_run.py TEST.js [--url URL] [--prepend FILE]"""
import argparse, asyncio, json, os, subprocess, sys, tempfile, time, urllib.request
import websockets

S = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument("test")
ap.add_argument("--url", default="http://localhost:8000/")
ap.add_argument("--prepend")
args = ap.parse_args()
TEST_JS = open(args.test).read()
if args.prepend:
    TEST_JS = open(args.prepend).read() + "\n;\n" + TEST_JS
PORT = 9333


async def main():
    proc = subprocess.Popen(
        ["/usr/bin/chromium-browser", "--headless=new", f"--remote-debugging-port={PORT}",
         f"--user-data-dir={tempfile.mkdtemp(dir=S)}", "--no-first-run", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=1)
                break
            except Exception:
                time.sleep(0.2)
        tgt = json.load(urllib.request.urlopen(urllib.request.Request(
            f"http://127.0.0.1:{PORT}/json/new?about:blank", method="PUT")))
        async with websockets.connect(tgt["webSocketDebuggerUrl"], max_size=None) as ws:
            n, errors, loaded = 0, [], asyncio.Event()

            async def send(method, params=None):
                nonlocal n
                n += 1
                my = n
                await ws.send(json.dumps({"id": my, "method": method, "params": params or {}}))
                while True:
                    msg = json.loads(await ws.recv())
                    if msg.get("id") == my:
                        return msg
                    m = msg.get("method")
                    if m == "Runtime.exceptionThrown":
                        d = msg["params"]["exceptionDetails"]
                        errors.append((d.get("exception") or {}).get("description") or d.get("text"))
                    elif m == "Runtime.consoleAPICalled" and msg["params"]["type"] == "error":
                        errors.append(" ".join(str(a.get("value", a.get("description"))) for a in msg["params"]["args"]))
                    elif m == "Page.loadEventFired":
                        loaded.set()

            await send("Runtime.enable")
            await send("Page.enable")
            await send("Network.enable")
            await send("Emulation.setFocusEmulationEnabled", {"enabled": True})  # headless: make focus/blur fire
            await send("Network.setCacheDisabled", {"cacheDisabled": True})      # always the fresh index.html
            await send("Page.navigate", {"url": args.url})
            for _ in range(50):
                if loaded.is_set():
                    break
                await send("Runtime.evaluate", {"expression": "1"})
                await asyncio.sleep(0.1)
            await asyncio.sleep(1.0)
            r = await send("Runtime.evaluate", {"expression": TEST_JS, "awaitPromise": True, "returnByValue": True})
            res = r.get("result", {})
            if "exceptionDetails" in res:
                print("TEST SCRIPT ERROR:", res["exceptionDetails"].get("exception", {}).get("description"))
                return 2
            results = json.loads(res["result"]["value"])
            fails = 0
            for name, ok, detail in results:
                fails += not ok
                print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"\n      {detail}"))
            print(f"\npage errors during load/test: {errors or 'none'}")
            print(f"{len(results) - fails}/{len(results)} passed")
            return 1 if fails or errors else 0
    finally:
        proc.terminate()


sys.exit(asyncio.run(main()))
```

`$S/ui/ui_shot.py` screenshots one element of the live page at a given width (view the PNG with the Read tool):

```python
"""Usage: python3 ui_shot.py WIDTH CSS_SELECTOR OUT.png [JS_TO_RUN_FIRST]"""
import asyncio, base64, json, os, subprocess, sys, tempfile, time, urllib.request
import websockets

S = os.path.dirname(os.path.abspath(__file__))
WIDTH, SEL, OUT = int(sys.argv[1]), sys.argv[2], sys.argv[3]
PRE = sys.argv[4] if len(sys.argv) > 4 else ""
PORT = 9334


async def main():
    proc = subprocess.Popen(
        ["/usr/bin/chromium-browser", "--headless=new", f"--remote-debugging-port={PORT}",
         f"--user-data-dir={tempfile.mkdtemp(dir=S)}", "--no-first-run", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=1)
                break
            except Exception:
                time.sleep(0.2)
        tgt = json.load(urllib.request.urlopen(urllib.request.Request(
            f"http://127.0.0.1:{PORT}/json/new?about:blank", method="PUT")))
        async with websockets.connect(tgt["webSocketDebuggerUrl"], max_size=None) as ws:
            n = 0

            async def send(method, params=None):
                nonlocal n
                n += 1
                my = n
                await ws.send(json.dumps({"id": my, "method": method, "params": params or {}}))
                while True:
                    msg = json.loads(await ws.recv())
                    if msg.get("id") == my:
                        return msg

            await send("Network.enable")
            await send("Network.setCacheDisabled", {"cacheDisabled": True})
            await send("Emulation.setDeviceMetricsOverride",
                       {"width": WIDTH, "height": 2600, "deviceScaleFactor": 1, "mobile": False})
            await send("Page.navigate", {"url": "http://localhost:8000/"})
            await asyncio.sleep(2.5)
            if PRE:
                await send("Runtime.evaluate", {"expression": PRE, "awaitPromise": True})
                await asyncio.sleep(0.5)
            r = await send("Runtime.evaluate", {"expression":
                f"JSON.stringify((()=>{{const b=document.querySelector({json.dumps(SEL)}).getBoundingClientRect();return [b.x,b.y+window.scrollY,b.width,b.height];}})())",
                "returnByValue": True})
            x, y, w, h = json.loads(r["result"]["result"]["value"])
            shot = await send("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True,
                              "clip": {"x": x, "y": y, "width": w, "height": h, "scale": 1}})
            open(OUT, "wb").write(base64.b64decode(shot["result"]["data"]))
            print("saved", OUT, int(w), "x", int(h))
    finally:
        proc.terminate()


asyncio.run(main())
```

- [ ] **Step 2: Write the failing UI test**

`$S/ui/hb_ui_test.js` (all writes are intercepted; `/api/state` is the real response with a test `hold_breath` dict swapped in):

```js
(async()=>{
  const out=[],sleep=ms=>new Promise(r=>setTimeout(r,ms));
  const check=(n,ok,d)=>out.push([n,!!ok,String(d)]);
  const el=id=>document.getElementById(id);
  const real=window.fetch.bind(window),posts=[];
  const HB={enabled:true,trigger:'M4',ads_mode:'toggle',breath_mode:'toggle',key:'leftshift',tap_on_release:true,delay_ms:150,max_hold_ms:3000};
  window.fetch=async(u,o={})=>{
    if((o.method||'GET').toUpperCase()!=='GET'){
      const b=o.body?JSON.parse(o.body):null;posts.push([u,b]);
      if(b&&b.delay_ms===5000)return new Response(JSON.stringify({detail:'delay_ms must be 0-2000'}),{status:400});
      if(u.endsWith('/toggle'))return new Response(JSON.stringify({enabled:false}),{status:200});
      return new Response(JSON.stringify({ok:true}),{status:200});
    }
    if(u==='/api/state'){const d=await (await real(u,o)).json();d.hold_breath=Object.assign({},HB);return new Response(JSON.stringify(d),{status:200});}
    if(u.startsWith('/api/streamdeck')&&window._sd)return new Response(JSON.stringify(window._sd),{status:200});
    return real(u,o);
  };
  // Live /ws pushes from the real server would overwrite the header mid-test.
  const realApply=applyStatus;window.applyStatus=()=>{};
  const HBURL='/api/hold_breath';
  const last=url=>{const p=posts.filter(x=>x[0]===url).pop();return p?JSON.stringify(p[1]):undefined;};
  const change=(id,v)=>{const e=el(id);if(e.type==='checkbox')e.checked=v;else e.value=v;e.dispatchEvent(new Event('change'));};

  const tabs=[...document.querySelectorAll('#tabbar .tab')].map(t=>t.dataset.tab);
  check('tab sits between Flashlight and Tools', tabs.indexOf('holdbreath')===tabs.indexOf('flashlight')+1&&tabs.indexOf('tools')===tabs.indexOf('holdbreath')+1, tabs);
  st('holdbreath');await sleep(50);
  check('Hold Breath panel shows', el('tab-holdbreath')&&el('tab-holdbreath').classList.contains('active'), el('tab-holdbreath')&&el('tab-holdbreath').className);

  await loadState();await sleep(200);
  check('loads settings from /api/state', el('hb-en').checked&&el('hb-trig').value==='M4'&&el('hb-ads').value==='toggle'&&el('hb-bm').value==='toggle'&&el('hb-tap').checked&&el('hb-delay').value==='150'&&el('hb-max').value==='3000'&&el('hb-key').value==='leftshift',
    [el('hb-en').checked,el('hb-trig').value,el('hb-ads').value,el('hb-bm').value,el('hb-tap').checked,el('hb-delay').value,el('hb-max').value,el('hb-key').value].join(','));
  check('trigger offers RMB, MMB, M4, M5 only', [...el('hb-trig').options].map(o=>o.value).join(',')==='RMB,MMB,M4,M5', [...el('hb-trig').options].map(o=>o.value));
  check('tap-again row visible for toggle breath', el('hb-tap-row').style.display!=='none', el('hb-tap-row').style.display);

  change('hb-ads','hold');await sleep(80);
  check('ADS posts only {ads_mode}', last(HBURL)==='{"ads_mode":"hold"}', last(HBURL));
  change('hb-bm','hold');await sleep(80);
  check('breath mode posts {breath_mode} and hides tap-again', last(HBURL)==='{"breath_mode":"hold"}'&&el('hb-tap-row').style.display==='none', last(HBURL));
  change('hb-trig','MMB');await sleep(80);
  check('trigger posts {trigger}', last(HBURL)==='{"trigger":"MMB"}', last(HBURL));
  change('hb-delay','200');await sleep(80);
  check('delay posts {delay_ms:200}', last(HBURL)==='{"delay_ms":200}', last(HBURL));
  change('hb-max','0');await sleep(80);
  check('max hold posts {max_hold_ms:0}', last(HBURL)==='{"max_hold_ms":0}', last(HBURL));
  change('hb-en',false);await sleep(80);
  check('enable switch posts {enabled:false}', last(HBURL)==='{"enabled":false}', last(HBURL));
  change('hb-bm','toggle');await sleep(80);change('hb-tap',false);await sleep(80);
  check('tap-again posts {tap_on_release:false}', last(HBURL)==='{"tap_on_release":false}', last(HBURL));

  change('hb-delay','5000');await sleep(400);
  check('rejected value: server message shown, field restored', /0-2000/.test(el('notif').textContent)&&el('hb-delay').value==='150', `${el('notif').textContent} / ${el('hb-delay').value}`);

  el('hb-key').focus();el('hb-key').dispatchEvent(new KeyboardEvent('keydown',{code:'KeyV',key:'v',bubbles:true,cancelable:true}));await sleep(120);
  check('press V binds v', last(HBURL)==='{"key":"v"}'&&el('hb-key').value==='V', `${last(HBURL)} ${el('hb-key').value}`);
  el('hb-key').focus();el('hb-key').dispatchEvent(new KeyboardEvent('keydown',{code:'Escape',key:'Escape',bubbles:true,cancelable:true}));await sleep(80);
  check('Esc cancels and keeps V', last(HBURL)==='{"key":"v"}'&&el('hb-key').value==='V', `${last(HBURL)} ${el('hb-key').value}`);
  el('hb-key-clear').click();await sleep(120);
  check('Clear posts NONE', last(HBURL)==='{"key":"NONE"}'&&el('hb-key').value==='NONE', `${last(HBURL)} ${el('hb-key').value}`);

  st('flashlight');await sleep(50);
  el('fl-key').focus();el('fl-key').dispatchEvent(new KeyboardEvent('keydown',{code:'KeyF',key:'f',bubbles:true,cancelable:true}));await sleep(120);
  check('Flashlight Key still binds through the shared helper', last('/api/flashlight')==='{"key":"f"}'&&el('fl-key').value==='F', `${last('/api/flashlight')} ${el('fl-key').value}`);
  el('fl-key-clear').click();await sleep(120);
  check('Flashlight Clear still works', last('/api/flashlight')==='{"key":"NONE"}', last('/api/flashlight'));

  check('header cards: Recoil, Flashlight, Hold Breath, Script', ['sc-recoil','sc-flash','sc-hb','sc-script'].every(id=>el(id)&&el(id).parentElement.id==='sp'), [...el('sp').children].map(c=>c.id));
  realApply({makcu_connected:true,recoil_enabled:true,flashlight_active:false,flashlight_enabled:false,loaded_script:'X',hold_breath_enabled:true,hold_breath_active:true,hold_breath_ads_mode:'toggle'});
  check('card ON with master and ADS mode', el('sc-hb').classList.contains('on')&&el('sc-hb-v').textContent==='ON'&&el('sc-hb-master').textContent==='Master: ON · toggle', `${el('sc-hb').className} | ${el('sc-hb-v').textContent} | ${el('sc-hb-master').textContent}`);
  realApply({makcu_connected:true,recoil_enabled:false,flashlight_active:false,loaded_script:'X',hold_breath_enabled:true,hold_breath_active:false,hold_breath_ads_mode:'hold'});
  check('card OFF while Recoil is off', !el('sc-hb').classList.contains('on')&&el('sc-hb-v').textContent==='OFF'&&el('sc-hb-master').textContent==='Master: ON · hold', `${el('sc-hb-v').textContent} | ${el('sc-hb-master').textContent}`);
  window.applyStatus=realApply;
  window._sd={recoil:true,flashlight:false,makcu:true,script:'X',hold_breath:true,hold_breath_ads:'toggle'};
  await pollMakcu();await sleep(80);
  check('REST fallback (pollMakcu) updates the card', el('sc-hb-v').textContent==='ON', el('sc-hb-v').textContent);
  window.applyStatus=()=>{};
  el('sc-hb').click();await sleep(120);
  check('tapping the card posts /api/hold_breath/toggle', posts.some(p=>p[0]==='/api/hold_breath/toggle'), posts.map(p=>p[0]).join(','));
  return JSON.stringify(out);
})()
```

- [ ] **Step 3: Run it and confirm it fails**

Run: `cd $S/ui && timeout 120 python3 ui_run.py hb_ui_test.js`
Expected: FAIL lines starting with "tab sits between Flashlight and Tools" (or a TEST SCRIPT ERROR about a null element).

- [ ] **Step 4: Header CSS and markup**

CSS: change the first `#sp` rule from `grid-template-columns:1fr 1fr;` to `grid-template-columns:repeat(3,1fr);` (the `@media(min-width:800px)` rule with `repeat(4,1fr)` stays). After the `.sc-master{...}` rule add:

```css
.sc-master.hb{right:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
```

Markup: in `<div id="sp">`, after the `sc-flash` card and before `sc-script`, add:

```html
  <div class="sc tap" id="sc-hb" onclick="toggleHoldBreath()"><div class="sc-lbl">Hold Breath</div><div class="sc-val" id="sc-hb-v">OFF</div><div class="sc-master hb" id="sc-hb-master">Master: OFF · hold</div></div>
```

(No "tap" hint on this card: the master line needs the width at 390 px.)

- [ ] **Step 5: Tab and panel markup**

After the Flashlight tab (`<div class="tab"        data-tab="flashlight" onclick="st('flashlight')">Flashlight</div>`) add:

```html
  <div class="tab"        data-tab="holdbreath" onclick="st('holdbreath')">Hold Breath</div>
```

After the end of the Flashlight panel (the `</div>\n</div>` that closes `<div class="panel" id="tab-flashlight">`, right before `<!-- ═══ TOOLS ═══ -->`) add:

```html
<!-- ═══ HOLD BREATH ═══ -->
<div class="panel" id="tab-holdbreath">
<div class="cfg">
  <div class="card">
    <div class="ch">Control</div>
    <div class="cb">
      <div class="crow"><span class="lbl">Enable Hold Breath</span><div class="ctl"><label class="tog"><input type="checkbox" id="hb-en" onchange="hbSet({enabled:this.checked})"><div class="tog-tr"></div></label></div></div>
      <div class="crow"><span class="lbl">Aim Mouse Button</span><div class="ctl"><select id="hb-trig" onchange="hbSet({trigger:this.value})"><option>RMB</option><option>MMB</option><option>M4</option><option>M5</option></select></div></div>
      <div class="crow"><span class="lbl">ADS</span><div class="ctl"><select id="hb-ads" onchange="hbSet({ads_mode:this.value})" title="Hold: the game aims while the button is held. Toggle: each click starts or stops aiming."><option value="hold">Hold</option><option value="toggle">Toggle</option></select></div></div>
      <div class="crow"><span class="lbl">Breath Key</span><div class="ctl"><select id="hb-bm" onchange="hbSet({breath_mode:this.value});hbShowTap()" title="Hold: the key is held down while breathing. Toggle: one tap starts, another tap stops."><option value="hold">Hold</option><option value="toggle">Toggle</option></select></div></div>
      <div class="crow" id="hb-tap-row" style="display:none"><span class="lbl">Tap Again When Aiming Ends</span><div class="ctl"><label class="tog"><input type="checkbox" id="hb-tap" onchange="hbSet({tap_on_release:this.checked})"><div class="tog-tr"></div></label></div></div>
      <div class="crow"><span class="lbl">Hold Breath Key</span><div class="ctl"><input type="text" id="hb-key" class="fl-key" value="NONE" autocomplete="off" spellcheck="false" title="Click, then press the key your game uses to hold breath. On a phone, type its name (shift, f, space) and press Enter."><button class="btn sm" id="hb-key-clear" onclick="_hbKB.set('NONE')">Clear</button></div></div>
    </div>
  </div>
  <div class="card">
    <div class="ch">Timing</div>
    <div class="cb">
      <div class="crow"><span class="lbl">Delay After Aiming (ms)</span><div class="ctl"><input type="number" id="hb-delay" min="0" max="2000" value="0" onchange="hbSet({delay_ms:fv(this)||0})"></div></div>
      <div class="crow"><span class="lbl">Max Hold (ms, 0 = no limit)</span><div class="ctl"><input type="number" id="hb-max" min="0" max="30000" value="0" onchange="hbSet({max_hold_ms:fv(this)||0})"></div></div>
    </div>
  </div>
  <div class="card"><p class="note">Hold Breath only works when <strong>Recoil is ON</strong> and a key is bound. When you aim, Helix waits the delay, then holds or taps the key; it lets go when you stop aiming or after the max hold. With ADS set to Toggle, Helix counts your clicks: if the game leaves aim without a click (sprint, reload, inventory), right-click twice to get back in step.</p></div>
</div>
</div>
```

- [ ] **Step 6: JavaScript**

1. Replace the whole Flashlight Key block, from the comment line `// ── Flashlight Key: click the box, press a key (phones: type the name, Enter) ──` down to and including the IIFE that ends with `})();` just before `function useBurst(ms){`, with this shared version (same behaviour, now usable by any key box):

```js
// ── Key binding boxes (Flashlight Key, Hold Breath Key): click the box, press a key ──
// (phones: type the key name, Enter). Esc cancels. POSTs {key} to the box's endpoint.
const _KEY_CODES={Enter:'enter',Backspace:'backspace',Tab:'tab',Space:'space',Minus:'minus',Equal:'equals',
  BracketLeft:'leftbracket',BracketRight:'rightbracket',Backslash:'backslash',Semicolon:'semicolon',Quote:'quote',
  Backquote:'grave',Comma:'comma',Period:'period',Slash:'slash',CapsLock:'capslock',PrintScreen:'printscreen',
  ScrollLock:'scrolllock',Pause:'pause',Insert:'insert',Home:'home',PageUp:'pageup',Delete:'delete',End:'end',
  PageDown:'pagedown',ArrowRight:'right',ArrowLeft:'left',ArrowDown:'down',ArrowUp:'up',NumLock:'numlock',
  NumpadDivide:'kpdivide',NumpadMultiply:'kpmultiply',NumpadSubtract:'kpminus',NumpadAdd:'kpplus',
  NumpadEnter:'kpenter',NumpadDecimal:'kpperiod',ControlLeft:'leftctrl',ShiftLeft:'leftshift',AltLeft:'leftalt',
  MetaLeft:'leftgui',ControlRight:'rightctrl',ShiftRight:'rightshift',AltRight:'rightalt',MetaRight:'rightgui'};
function keyFromCode(c){
  let m;
  if((m=/^Key([A-Z])$/.exec(c)))return m[1].toLowerCase();
  if((m=/^Digit(\d)$/.exec(c)))return m[1];
  if((m=/^F(\d{1,2})$/.exec(c))&&+m[1]>=1&&+m[1]<=12)return 'f'+m[1];
  if((m=/^Numpad(\d)$/.exec(c)))return 'kp'+m[1];
  return _KEY_CODES[c]||null;
}
function keyLabel(k){return !k||k==='NONE'?'NONE':(k.length===1||/^f\d+$/.test(k))?k.toUpperCase():k;}
function keyBinder(inputId,url){
  const b={key:'NONE',capturing:false};
  b.show=k=>{b.key=k||'NONE';const i=$(inputId);if(i&&!b.capturing)i.value=keyLabel(b.key);};
  b.set=async k=>{
    const i=$(inputId);b.capturing=false;
    try{await api(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:k})});b.show(k.toLowerCase()==='none'?'NONE':k.trim().toLowerCase());}
    catch(e){notify(recErr(e));b.show(b.key);}
    if(i&&document.activeElement===i)i.blur();
  };
  const i=$(inputId);
  if(i){
    i.addEventListener('focus',()=>{b.capturing=true;i.value='';i.placeholder='Press a key…';});
    i.addEventListener('blur',()=>{
      const typed=i.value.trim();i.placeholder='';
      if(b.capturing&&typed){b.set(typed);return;}
      b.capturing=false;i.value=keyLabel(b.key);
    });
    i.addEventListener('keydown',e=>{
      if(e.key==='Escape'){e.preventDefault();b.capturing=false;i.value=keyLabel(b.key);i.blur();return;}
      if(e.key==='Enter'&&i.value.trim()){e.preventDefault();b.set(i.value.trim());return;}
      const k=keyFromCode(e.code);
      if(k){e.preventDefault();b.set(k);}
    });
  }
  return b;
}
const _flKB=keyBinder('fl-key','/api/flashlight'),_hbKB=keyBinder('hb-key','/api/hold_breath');
function flKeyShow(k){_flKB.show(k);}
function flKeySet(k){return _flKB.set(k);}
// ── Hold Breath tab ──
function hbShowTap(){const r=$('hb-tap-row');if(r)r.style.display=$('hb-bm').value==='toggle'?'':'none';}
function hbApply(h){
  chk('hb-en',h.enabled);sel('hb-trig',h.trigger||'RMB');sel('hb-ads',h.ads_mode||'hold');sel('hb-bm',h.breath_mode||'hold');
  chk('hb-tap',h.tap_on_release);num('hb-delay',h.delay_ms??0);num('hb-max',h.max_hold_ms??0);_hbKB.show(h.key||'NONE');hbShowTap();
}
async function hbLoad(){try{const d=await api('/api/state');hbApply(d.hold_breath||{});}catch(e){}}
async function hbSet(body){
  try{await api('/api/hold_breath',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});}
  catch(e){notify(recErr(e));hbLoad();}   // show why, and put the controls back to what the server has
}
```

2. After `async function toggleFlashlight(){...}` (3 lines) add:

```js
async function toggleHoldBreath(){
  try{const d=await api('/api/hold_breath/toggle',{method:'POST'});chk('hb-en',d.enabled);notify(d.enabled?'● Hold Breath ON':'● Hold Breath OFF');}
  catch(e){notify('Toggle failed');}
}
```

3. In `loadState`, right after the line that starts `chk('fl-en',fl.enabled);sel('fl-kb',fl.keybind||'NONE');`, add:

```js
    hbApply(d.hold_breath||{});
```

(`loadState` holds the `/api/state` response in `d`; the line above it reads `const r=d.recoil||{},fl=d.flashlight||{},s=d.settings||{};`.)

4. In `applyStatus`, after the line `if(d.flashlight_enabled!==undefined){const m=$('sc-flash-master');...}` add:

```js
  if(d.hold_breath_active!==undefined){card('sc-hb',d.hold_breath_active?'on':'');$('sc-hb-v').textContent=d.hold_breath_active?'ON':'OFF';}
  if(d.hold_breath_enabled!==undefined){const m=$('sc-hb-master');if(m)m.textContent=`Master: ${d.hold_breath_enabled?'ON':'OFF'} · ${d.hold_breath_ads_mode||'hold'}`;chk('hb-en',d.hold_breath_enabled);}
```

5. In `pollMakcu`, change the `applyStatus({...})` call to also pass `hold_breath_active:d.hold_breath`:

```js
    applyStatus({makcu_connected:d.makcu,recoil_enabled:d.recoil,flashlight_active:d.flashlight,loaded_script:d.script,hold_breath_active:d.hold_breath});
```

- [ ] **Step 7: Run the UI test and confirm it passes**

Run: `cd $S/ui && timeout 120 python3 ui_run.py hb_ui_test.js`
Expected: all PASS, `page errors during load/test: none`. If "loads settings" fails only on `hb-key`, check that `hbApply` runs after `_hbKB` is defined (the binder block must come before any call).

- [ ] **Step 8: Check the layout with screenshots**

```bash
cd $S/ui
python3 ui_shot.py 390 '#sp' sp_390.png
python3 ui_shot.py 1100 '#sp' sp_1100.png
python3 ui_shot.py 390 '#tabbar' tabs_390.png
python3 ui_shot.py 390 '#tab-holdbreath .cfg' hb_390.png "st('holdbreath')"
```

Open each PNG with the Read tool. Check: at 390 px the three tap cards sit in one row with Script below, and "Master: OFF · hold" is not cut off mid-word or overlapping; at 1100 px there are four cards in one row; the tab bar shows "Hold Breath" (it may scroll sideways, which is existing behaviour); the Hold Breath panel rows are aligned like the Flashlight tab. Fix spacing in CSS if anything overlaps, then re-shoot.

- [ ] **Step 9: Commit**

```bash
cd /home/jason/Downloads/final/Helix
git add static/index.html
git commit -m "ui: Hold Breath tab and header card; key binding shared with the Flashlight Key

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
git fetch -q origin && git log --oneline HEAD..origin/main   # must print nothing
git push -q origin main
```

---

### Task 6: Stream Deck "Toggle Hold Breath" action

**Files:**
- Modify: `streamdeck/com.helix.sdPlugin/manifest.json`, `streamdeck/com.helix.sdPlugin/plugin.js`
- Create: `streamdeck/com.helix.sdPlugin/icons/holdbreath-on.svg`, `streamdeck/com.helix.sdPlugin/icons/holdbreath-off.svg`
- Test: `$S/ui/sd_test.js` (runs `plugin.js` in a blank page with fakes)

**Interfaces:**
- Consumes: `GET /api/streamdeck` keys `hold_breath` (bool), `hold_breath_ads` (`hold`/`toggle`); `POST /api/hold_breath/toggle`. Plugin internals: `onKeyDown(msg)`, `onWillAppear(msg)`, `pollState(done)`, `setIconForContext(ctx, action, state)`, `sendSD(event, context, payload)` (needs `websocket.readyState===1`), globals `websocket`, `globalSettings`, `pollBusy`, `stopPolling()`.
- Produces: action UUID `com.helix.holdbreath`; `renderHoldBreathIcon(on, ads, error) -> svg string`.

- [ ] **Step 1: Write the failing test**

`$S/ui/sd_test.js`:

```js
(async()=>{
  const out=[],sleep=ms=>new Promise(r=>setTimeout(r,ms));
  const check=(n,ok,d)=>out.push([n,!!ok,String(d)]);
  const sent=[],fetched=[];
  websocket={readyState:1,send:m=>sent.push(JSON.parse(m))};
  window._sd={recoil:true,flashlight:false,makcu:true,script:'ABI/X',hold_breath:true,hold_breath_ads:'toggle'};
  window.fetch=async(u,o={})=>{fetched.push([u,(o.method||'GET')]);
    if(u.indexOf('/api/streamdeck')>=0)return new Response(JSON.stringify(window._sd),{status:200});
    return new Response('{}',{status:200});};
  globalSettings={serverUrl:'http://helix:8000'};
  const img=ctx=>{const m=sent.filter(s=>s.event==='setImage'&&s.context===ctx).pop();return m?decodeURIComponent(escape(atob(m.payload.image.split(',')[1]))):'';};

  onWillAppear({context:'hb',action:'com.helix.holdbreath',payload:{settings:{}}});
  onWillAppear({context:'rc',action:'com.helix.recoil',payload:{settings:{}}});
  // The second willAppear does not poll (polling is already running); poll once now
  // instead of waiting for the 1 s tick.
  await sleep(100);pollBusy=false;await new Promise(r=>pollState(r));await sleep(50);
  check('Hold Breath icon: BREATH, ON, TOGGLE', /BREATH/.test(img('hb'))&&/>ON</.test(img('hb'))&&/TOGGLE/.test(img('hb')), img('hb').slice(0,120));
  check('Recoil icon still renders', /RECOIL/.test(img('rc'))&&/>ON</.test(img('rc')), img('rc').slice(0,80));
  window._sd=Object.assign({},window._sd,{hold_breath:false,hold_breath_ads:'hold'});pollBusy=false;
  await new Promise(r=>pollState(r));await sleep(50);
  check('state change redraws: OFF, HOLD', />OFF</.test(img('hb'))&&/HOLD/.test(img('hb')), img('hb').slice(0,120));
  onKeyDown({action:'com.helix.holdbreath',context:'hb',payload:{settings:{}}});await sleep(80);
  check('key press posts /api/hold_breath/toggle', fetched.some(f=>f[0]==='http://helix:8000/api/hold_breath/toggle'&&f[1]==='POST'), JSON.stringify(fetched));
  window.fetch=async()=>{throw new Error('down');};pollBusy=false;
  await new Promise(r=>pollState(r));await sleep(50);
  check('server down: dash shown', /—/.test(img('hb')), img('hb').slice(0,120));
  stopPolling();
  return JSON.stringify(out);
})()
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `cd $S/ui && timeout 120 python3 ui_run.py sd_test.js --url about:blank --prepend /home/jason/Downloads/final/Helix/streamdeck/com.helix.sdPlugin/plugin.js`
Expected: FAIL "Hold Breath icon: BREATH, ON, TOGGLE" (no image for that action yet) and FAIL on the key press check.

- [ ] **Step 3: Implement in `plugin.js`**

In `onKeyDown`, after `if (action === 'com.helix.flashlight') endpoint = '/api/flashlight/toggle';` add:

```js
    if (action === 'com.helix.holdbreath') endpoint = '/api/hold_breath/toggle';
```

In `setIconForContext`, after the `com.helix.flashlight` branch add:

```js
    } else if (action === 'com.helix.holdbreath') {
        svg = renderHoldBreathIcon(err ? false : state.hold_breath, err ? null : state.hold_breath_ads, err);
```

(keep the `else if` chain intact: this goes between the flashlight branch and the `com.helix.cycle` branch.)

After `renderFlashlightIcon(...)`'s closing brace add:

```js
function renderHoldBreathIcon(on, ads, error) {
    var c  = error ? '#ff4444' : (on ? '#33ccff' : '#ff4444');
    var bc = error ? '#2a1818' : (on ? '#15303a' : '#2a1818');
    var op = error ? 0.3 : (on ? 1 : 0.45);
    var lb = error ? '—' : (on ? 'ON' : 'OFF');
    var mode = (error || !ads) ? '' : (ads === 'toggle' ? 'TOGGLE' : 'HOLD');

    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 144 144" width="144" height="144">'
        + '<defs><filter id="g"><feGaussianBlur stdDeviation="3.5" result="b"/>'
        + '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>'
        + '<rect width="144" height="144" rx="18" fill="#0f1012" stroke="' + bc + '" stroke-width="1.5"/>'
        + (on ? '<rect x="16" y="137" width="112" height="4" rx="2" fill="' + c + '" opacity="0.35"/>' : '')
        + '<g transform="translate(72,36)" opacity="' + op + '"' + (on ? ' filter="url(#g)"' : '') + '>'
        + '<circle r="20" fill="none" stroke="' + c + '" stroke-width="2.5"/>'
        + '<path d="M-14 0 Q-7 -8 0 0 T14 0" fill="none" stroke="' + c + '" stroke-width="2.5" stroke-linecap="round"/>'
        + '<circle r="2.5" fill="' + c + '"/>'
        + '</g>'
        + (mode ? '<text x="72" y="73" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-weight="700" font-size="12" fill="' + c + '" letter-spacing="1.5" opacity="' + (on ? 0.8 : 0.45) + '">' + mode + '</text>' : '')
        + '<text x="72" y="100" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-weight="700" font-size="19" fill="' + c + '" letter-spacing="2" opacity="' + (on ? 1 : 0.55) + '">BREATH</text>'
        + '<text x="72" y="128" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-weight="700" font-size="24" fill="' + c + '" opacity="' + (on ? 0.9 : 0.5) + '">' + lb + '</text>'
        + '</svg>';
}
```

- [ ] **Step 4: Manifest and static icons**

In `manifest.json`, change `"Version": "1.0.0"` to `"Version": "1.1.0"`, and add this action object after the `com.helix.flashlight` action (mind the commas):

```json
        {
            "Icon": "icons/holdbreath-on",
            "Name": "Toggle Hold Breath",
            "States": [
                { "Image": "icons/holdbreath-off" },
                { "Image": "icons/holdbreath-on" }
            ],
            "SupportedInMultiActions": true,
            "Tooltip": "Toggle Helix hold breath on/off. Icon shows ON/OFF and the ADS mode.",
            "UUID": "com.helix.holdbreath"
        },
```

`icons/holdbreath-on.svg`:

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 144 144" width="144" height="144">
  <defs>
    <filter id="glow">
      <feGaussianBlur stdDeviation="3.5" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>
  <rect width="144" height="144" rx="18" fill="#0f1012" stroke="#15303a" stroke-width="1.5"/>
  <rect x="16" y="137" width="112" height="4" rx="2" fill="#33ccff" opacity="0.35"/>
  <g transform="translate(72,36)" filter="url(#glow)">
    <circle r="20" fill="none" stroke="#33ccff" stroke-width="2.5"/>
    <path d="M-14 0 Q-7 -8 0 0 T14 0" fill="none" stroke="#33ccff" stroke-width="2.5" stroke-linecap="round"/>
    <circle r="2.5" fill="#33ccff"/>
  </g>
  <text x="72" y="100" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-weight="700" font-size="19" fill="#33ccff" letter-spacing="2">BREATH</text>
  <text x="72" y="128" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-weight="700" font-size="24" fill="#33ccff" opacity="0.9">ON</text>
</svg>
```

`icons/holdbreath-off.svg`:

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 144 144" width="144" height="144">
  <rect width="144" height="144" rx="18" fill="#0f1012" stroke="#2a1818" stroke-width="1.5"/>
  <g transform="translate(72,36)" opacity="0.45">
    <circle r="20" fill="none" stroke="#ff4444" stroke-width="2.5"/>
    <path d="M-14 0 Q-7 -8 0 0 T14 0" fill="none" stroke="#ff4444" stroke-width="2.5" stroke-linecap="round"/>
    <circle r="2.5" fill="#ff4444"/>
  </g>
  <text x="72" y="100" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-weight="700" font-size="19" fill="#ff4444" letter-spacing="2" opacity="0.55">BREATH</text>
  <text x="72" y="128" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-weight="700" font-size="24" fill="#ff4444" opacity="0.5">OFF</text>
</svg>
```

- [ ] **Step 5: Run the tests and check the manifest**

```bash
cd $S/ui && timeout 120 python3 ui_run.py sd_test.js --url about:blank --prepend /home/jason/Downloads/final/Helix/streamdeck/com.helix.sdPlugin/plugin.js
python3 -c "import json;m=json.load(open('/home/jason/Downloads/final/Helix/streamdeck/com.helix.sdPlugin/manifest.json'));print(m['Version'],[a['UUID'] for a in m['Actions']])"
python3 -c "import xml.dom.minidom as d;[d.parse('/home/jason/Downloads/final/Helix/streamdeck/com.helix.sdPlugin/icons/holdbreath-'+s+'.svg') for s in ('on','off')];print('svg ok')"
```

Expected: all PASS with no page errors; `1.1.0 ['com.helix.recoil', 'com.helix.flashlight', 'com.helix.holdbreath', 'com.helix.cycle', 'com.helix.status']`; `svg ok`.

- [ ] **Step 6: Commit**

```bash
cd /home/jason/Downloads/final/Helix
git add streamdeck/com.helix.sdPlugin/manifest.json streamdeck/com.helix.sdPlugin/plugin.js streamdeck/com.helix.sdPlugin/icons/holdbreath-on.svg streamdeck/com.helix.sdPlugin/icons/holdbreath-off.svg
git commit -m "feat: Stream Deck Toggle Hold Breath action (plugin 1.1.0)

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
git fetch -q origin && git log --oneline HEAD..origin/main   # must print nothing
git push -q origin main
```

---

### Task 7: Documentation, final verification, hand-off

**Files:**
- Modify: `README.md`, `streamdeck/SETUP.md`, `CLAUDE.md`, `docs/superpowers/specs/2026-10-09-hold-breath-design.md` (log example only)

- [ ] **Step 1: README**

Make these edits (keep the README's existing tone: plain, second person, short tables):
1. **Status Panel** (section `## Status Panel`): "Below it are three live cards" → "four live cards"; add this table row after the Flashlight row:
   `| **Hold Breath** | `ON` only when both Hold Breath and Recoil are enabled — tap to toggle the Hold Breath master switch. The card also shows `Master: ON/OFF` and the ADS mode (`hold` or `toggle`) |`
2. **New section** between the Flashlight Tab section (it ends with the "> Flashlight only fires when…" line and a `---`) and `### Tools Tab`. Insert exactly:

```markdown
### Hold Breath Tab

When you aim, the MAKCU presses your game's hold-breath key for you, so the scope steadies.

| Setting | What it does |
|---------|-------------|
| Enable Hold Breath | Master switch (same as tapping the Hold Breath status card). |
| Aim Mouse Button | The button you aim with: RMB (default), MMB, M4 or M5. |
| ADS | **Hold**: you aim while the button is held. **Toggle**: each click starts or stops aiming. Match your game's setting. |
| Breath Key | **Hold**: the key is held down while breathing. **Toggle**: one tap starts hold breath, another stops it. Match your game. |
| Tap Again When Aiming Ends | Toggle breath only: tap the key again when you stop aiming. Turn it on if your game keeps holding breath after you stop aiming. |
| Hold Breath Key | The game's hold-breath key. Click the box and press the key; on a phone, type its name (`shift`, `f`, `space`) and press Enter. Esc cancels, **Clear** sets NONE. |
| Delay After Aiming (ms) | Wait this long after you start aiming before holding breath (0–2000), so the scope-in animation can finish. |
| Max Hold (ms) | Stop holding breath after this long while still aiming (0–30000; 0 = no limit), so you don't run out of breath. |

> Hold Breath only works when **Recoil is ON** and a key is bound. With ADS set to Toggle, Helix counts your clicks; if the game leaves aim without a click (sprint, reload, inventory), right-click twice to get back in step. Any key Helix is holding is released when you stop aiming, when Hold Breath, Recoil or the key changes, when the MAKCU reconnects, and when the server stops.

---
```

3. **API Reference**: add after the `### Flashlight` table:

```markdown
### Hold Breath

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/hold_breath` | Update Hold Breath settings (partial update). Fields: `enabled`, `trigger` (`RMB`, `MMB`, `M4`, `M5`), `ads_mode` and `breath_mode` (`hold` or `toggle`), `key` (key name such as `shift`, `f`, `space`, or `NONE`), `tap_on_release`, `delay_ms` (0–2000), `max_hold_ms` (0–30000, 0 = no limit). Any invalid field returns 400 and nothing changes |
| POST | `/api/hold_breath/toggle` | Toggle Hold Breath on/off; returns `{"enabled": bool}` |

`GET /api/state` includes the same fields under `hold_breath`. The `/ws` message adds `hold_breath_enabled`, `hold_breath_active` (enabled and Recoil ON) and `hold_breath_ads_mode`.
```

4. **Stream Deck** API response example: add `"hold_breath": false,` and `"hold_breath_ads": "hold",` lines to the JSON block, and a sentence below it: "`hold_breath` is true only when Hold Breath and Recoil are both enabled."
5. **Stream Deck section** (`## Stream Deck`): "It provides four actions: **Toggle Recoil**, **Toggle Flashlight**, **Cycle Script** and a display-only **MAKCU Status**" → "It provides five actions: **Toggle Recoil**, **Toggle Flashlight**, **Toggle Hold Breath**, **Cycle Script** and a display-only **MAKCU Status**". Add: "After updating Helix, copy the plugin folder to the Stream Deck PC again (plugin version 1.1.0 adds Toggle Hold Breath)."
6. **Directory Structure** (the tree under `## Directory Structure`):
   - Under `routers/`, after the `flashlight.py` line, add: `│   ├── holdbreath.py             ← POST /api/hold_breath, /api/hold_breath/toggle`
   - Replace the line `├── mouse/makcu.py                ← MAKCU USB HID controller` with these three lines:
     ```
     ├── mouse/makcu.py                ← MAKCU USB HID controller
     ├── mouse/keyboard.py             ← Keyboard command queue (one key command at a time)
     ├── mouse/keys.py                 ← Key names → HID usages (vendor key table)
     ```
   - Under `features/`, after the `flashlight/` line, add: `│   ├── holdbreath/               ← Hold Breath state machine and loop`
   - Change `← Entire frontend (Recoil, Flashlight, Tools, Settings tabs; self-contained)` to `← Entire frontend (Recoil, Flashlight, Hold Breath, Tools, Settings tabs; self-contained)`

- [ ] **Step 2: streamdeck/SETUP.md**

Add a row after Toggle Flashlight in "Available Actions": `| **Toggle Hold Breath** | Toggles hold breath on/off | Cyan scope with HOLD/TOGGLE (ON) or dim red scope (OFF) |`. In the icons tree add `├── holdbreath-on.svg   (cyan scope)` and `├── holdbreath-off.svg  (red scope)` after the flashlight lines. In "Install" add a sentence: "When updating, replace the whole `com.helix.sdPlugin` folder and restart the Stream Deck software."

- [ ] **Step 3: CLAUDE.md**

1. Replace the existing bullet that starts `- The Flashlight Key is \`press_key()\`` with:

```markdown
- Every keyboard command goes through the one `KeyboardQueue` in `mouse/keyboard.py` (`mouse.makcu.keyboard`): `tap` = `km.press(<HID usage>,<ms>)`, `down`/`up` = `km.down`/`km.up`. The firmware runs one timed press or string at a time and answers `ERR` to any other key command sent during it; Helix does not read those replies, so the queue waits out each tap (+15 ms) before the next command. Never send `km.press`/`km.down`/`km.up` any other way. Names and aliases come from the vendor KM_API key table in `mouse/keys.py`; settings store the canonical name. The queue tracks keys held down; `release_all()` runs at shutdown. Keyboard injection is not yet confirmed on hardware.
- Hold Breath (`features/holdbreath/`): `machine.py` is pure logic (state table in `docs/superpowers/specs/2026-10-09-hold-breath-design.md`), `holdbreath.py` is the 5 ms loop. The loop sends key up for the configured key whenever the controller object changes (first connect or reconnect), so a key left down by a crash or dropped link is released. Toggle-ADS counts clicks and can get out of step by design (right-click twice).
```

2. In "Architecture (high level)", change the `features/` line to: "- `features/`: the long-running loops (recoil, flashlight, hold breath), the pattern recorder, and built-in CS2 patterns."

- [ ] **Step 4: Spec log example**

In the spec, the Behaviour section says the log looks like `[HoldBreath] down leftshift (aimed 152 ms)`. Change the example to what the code prints: `[HoldBreath] down leftshift` and `[HoldBreath] up leftshift`.

- [ ] **Step 5: Final verification (all of it, fresh)**

```bash
cd /home/jason/Downloads/final/Helix && python3 -m pytest -q -s $S/tests 2>&1 | tail -3
cd $S/ui && timeout 120 python3 ui_run.py hb_ui_test.js | tail -2
cd $S/ui && timeout 120 python3 ui_run.py sd_test.js --url about:blank --prepend /home/jason/Downloads/final/Helix/streamdeck/com.helix.sdPlugin/plugin.js | tail -2
curl -s -X POST localhost:8000/api/server/restart; echo
for i in $(seq 1 30); do sleep 1; curl -sf localhost:8000/api/device >/dev/null && break; done; sleep 2
curl -s localhost:8000/api/diagnostics | python3 -c "import json,sys;d=json.load(sys.stdin);print('commit',d['commit'],'| device',d['device']['firmware'],d['device']['baud'],'| stream',d['buttons']['stream_format'],'| hold_breath',d['hold_breath'])"
curl -s localhost:8000/api/streamdeck; echo
journalctl -u helix --since "-1min" --no-pager | grep -iE "traceback|unexpected error" || echo "log clean"
```

Expected: all host tests pass; both browser tests pass with no page errors; the server runs the latest commit, MAKCU connected at 4,000,000 baud, stream `km.+mask text`; `hold_breath` present; log clean. If anything fails, fix it before committing.

- [ ] **Step 6: Commit**

```bash
cd /home/jason/Downloads/final/Helix
git add README.md streamdeck/SETUP.md CLAUDE.md docs/superpowers/specs/2026-10-09-hold-breath-design.md
git commit -m "docs: Hold Breath (README, Stream Deck setup, CLAUDE.md gotchas)

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
git fetch -q origin && git log --oneline HEAD..origin/main   # must print nothing
git push -q origin main
```

- [ ] **Step 7: Report to the user**

Tell the user, plainly and in this order:
1. What is live (Hold Breath tab, header card, Stream Deck action) and that they only need to reload the page; the Stream Deck plugin folder must be copied to the Stream Deck PC again (version 1.1.0).
2. What was verified (host tests, browser tests, live server checks) and what was not: **no key press has been confirmed on the gaming PC yet** (neither the Flashlight Key nor Hold Breath).
3. How to test on hardware, step by step:
   - First the Flashlight Key: bind T, turn on Enable Flashlight and Recoil, hold fire past the hold threshold; the log shows `[Flashlight] Firing key t`; check that T arrives on the PC.
   - Then Hold Breath: bind the game's hold-breath key (often Shift), set ADS and Breath Key to match the game, turn on Enable Hold Breath and Recoil, aim; the log (`sudo journalctl -u helix -f`) shows `[HoldBreath] down leftshift` when you aim and `[HoldBreath] up leftshift` when you stop, and the scope should steady.
   - If the log shows the lines but nothing happens on the PC, the keyboard path itself is the problem; report back before changing anything else.
4. How to undo: `git revert` the Hold Breath commits (list their hashes).
