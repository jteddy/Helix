#!/usr/bin/env python3
"""
apply_patches.py
================
Run this from the root of your Cearum-Web repo:

    python3 apply_patches.py

It will:
  1. Back up the three files it modifies (.bak copies)
  2. Replace mouse/makcu.py with the fully corrected version
  3. Patch the one line in main.py  (Bug 7)
  4. Patch the two lines in static/index.html  (Bug 6)
  5. Print a summary of every change made
"""

import os
import re
import shutil
import sys

# -- Locate repo root (script must be run from there) -------------------------
REPO = os.path.dirname(os.path.abspath(__file__))

MAKCU_PATH  = os.path.join(REPO, "mouse", "makcu.py")
MAIN_PATH   = os.path.join(REPO, "main.py")
HTML_PATH   = os.path.join(REPO, "static", "index.html")

errors = []

def backup(path):
    bak = path + ".bak"
    shutil.copy2(path, bak)
    print(f"  OK Backed up -> {os.path.relpath(bak, REPO)}")

def check(path):
    if not os.path.exists(path):
        errors.append(f"File not found: {os.path.relpath(path, REPO)}")
        return False
    return True

# -----------------------------------------------------------------------------
# 1. mouse/makcu.py -- full replacement
# -----------------------------------------------------------------------------

MAKCU_CONTENT = '''\
import time
import threading
from makcu import create_controller, MouseButton


class makcu_controller:
    controller = None

    button_states = {
        "LMB": False,
        "RMB": False,
        "MMB": False,
        "M4":  False,
        "M5":  False,
    }

    connection_lock   = threading.Lock()
    command_lock      = threading.Lock()
    is_connected_flag = False

    # FIX 9: track thread object so we can check is_alive() instead of a bare bool
    _watchdog_thread: threading.Thread | None = None

    # FIX 5: set while move_mouse_smoothly is active -- watchdog skips its ping
    #         to avoid injecting a zero-move USB transaction mid-spray.
    _spray_active = threading.Event()

    # -- Shared helper ---------------------------------------------------------

    @staticmethod
    def _clear_button_states():
        """FIX 1: Hard-reset every button to False.
        Called on every disconnect path so the recoil loop never inherits
        a stale LMB=True from before the device dropped."""
        for k in makcu_controller.button_states:
            makcu_controller.button_states[k] = False

    # -- Public: connection state ----------------------------------------------

    @staticmethod
    def is_connected():
        with makcu_controller.connection_lock:
            return (
                makcu_controller.is_connected_flag
                and makcu_controller.controller is not None
            )

    # -- Watchdog --------------------------------------------------------------

    @staticmethod
    def _watchdog():
        """
        Background daemon thread.  Every 8 s it pings the device with a
        zero-movement command.  On failure it marks the device disconnected
        and keeps retrying connect() every 8 s until the MAKCU comes back.

        FIX 2: Because the library is now created with auto_reconnect=False,
        this watchdog is the single owner of reconnection logic.  There is no
        longer a race between the library\'s internal reconnect and ours.

        FIX 5: The watchdog skips its ping entirely while move_mouse_smoothly
        is executing (_spray_active is set) to prevent injecting a USB
        transaction mid-spray that could cause micro-stutter.
        """
        INTERVAL = 8  # seconds
        while True:
            time.sleep(INTERVAL)

            # -- Phase 1: device appears connected -- ping it -------------------
            with makcu_controller.connection_lock:
                connected = (
                    makcu_controller.is_connected_flag
                    and makcu_controller.controller is not None
                )
                ctrl = makcu_controller.controller if connected else None

            if connected:
                # FIX 5: skip the ping while a smooth-move spray is in progress
                if makcu_controller._spray_active.is_set():
                    continue

                try:
                    with makcu_controller.command_lock:
                        ctrl.move(0, 0)  # zero-move: exercises USB handle, no cursor movement
                except Exception as e:
                    print(f"[MAKCU] Watchdog detected disconnect: {e}")
                    with makcu_controller.connection_lock:
                        makcu_controller.is_connected_flag = False
                        makcu_controller.controller = None  # FIX 3
                    makcu_controller._clear_button_states()  # FIX 1

            # -- Phase 2: device is gone -- attempt reconnect -------------------
            else:
                print("[MAKCU] Watchdog attempting reconnect...")
                result = makcu_controller._do_connect()
                if result is not None:
                    print("[MAKCU] Watchdog reconnected successfully")

    # -- Core connect logic ----------------------------------------------------

    @staticmethod
    def _do_connect():
        """
        Core connection logic shared by connect() and the watchdog.
        Returns the controller on success, None on failure.

        FIX 2: auto_reconnect=False -- the library must NOT try to reconnect
        on its own.  If both the library\'s internal reconnect and our watchdog
        fire simultaneously they can open two overlapping HID connections,
        corrupt the USB state, and force a hard reset of the MAKCU.
        """
        try:
            controller = create_controller(debug=False, auto_reconnect=False)  # FIX 2

            def on_button_event(button: MouseButton, pressed: bool):
                if button == MouseButton.LEFT:
                    makcu_controller.button_states["LMB"] = pressed
                elif button == MouseButton.RIGHT:
                    makcu_controller.button_states["RMB"] = pressed
                elif button == MouseButton.MIDDLE:
                    makcu_controller.button_states["MMB"] = pressed
                elif button == MouseButton.MOUSE4:
                    makcu_controller.button_states["M4"] = pressed
                elif button == MouseButton.MOUSE5:
                    makcu_controller.button_states["M5"] = pressed

            controller.set_button_callback(on_button_event)
            controller.enable_button_monitoring(True)

            with makcu_controller.connection_lock:
                makcu_controller.controller = controller
                makcu_controller.is_connected_flag = True

            return controller

        except Exception as e:
            print(f"[MAKCU] Connection error: {e}")
            with makcu_controller.connection_lock:
                makcu_controller.is_connected_flag = False
                makcu_controller.controller = None  # FIX 3
            makcu_controller._clear_button_states()  # FIX 1
            return None

    @staticmethod
    def connect():
        with makcu_controller.connection_lock:
            if makcu_controller.controller is not None:
                return makcu_controller.controller

        result = makcu_controller._do_connect()

        # FIX 9: Start watchdog only if it isn\'t already alive.
        if result is not None:
            t = makcu_controller._watchdog_thread
            if t is None or not t.is_alive():
                new_t = threading.Thread(
                    target=makcu_controller._watchdog,
                    daemon=True,
                    name="makcu-watchdog",
                )
                new_t.start()
                makcu_controller._watchdog_thread = new_t
                print("[MAKCU] Watchdog started (8 s interval)")

        return result

    @staticmethod
    def StartButtonListener():
        makcu_controller.connect()

    # -- Command methods -------------------------------------------------------

    @staticmethod
    def click_button(button_name: str):
        if not makcu_controller.is_connected():
            return False
        mck = makcu_controller.controller
        try:
            with makcu_controller.command_lock:
                if button_name == "LMB":
                    mck.click(MouseButton.LEFT)
                elif button_name == "RMB":
                    mck.click(MouseButton.RIGHT)
                elif button_name == "MMB":
                    mck.click(MouseButton.MIDDLE)
                elif button_name == "M4":
                    mck.click(MouseButton.MOUSE4)
                elif button_name == "M5":
                    mck.click(MouseButton.MOUSE5)
            return True
        except Exception as e:
            print(f"[MAKCU] Click error: {e}")
            with makcu_controller.connection_lock:
                makcu_controller.is_connected_flag = False
                makcu_controller.controller = None  # FIX 3
            makcu_controller._clear_button_states()  # FIX 1
            return False

    @staticmethod
    def simple_move_mouse(x, y):
        if not makcu_controller.is_connected():
            return False
        try:
            with makcu_controller.command_lock:
                makcu_controller.controller.move(x, y)
            return True
        except Exception as e:
            print(f"[MAKCU] Move error: {e}")
            with makcu_controller.connection_lock:
                makcu_controller.is_connected_flag = False
                makcu_controller.controller = None  # FIX 3
            makcu_controller._clear_button_states()  # FIX 1
            return False

    @staticmethod
    def move_mouse_smoothly(dx, dy, steps=20, duration=0.05, interrupt_on_lmb_release=False):
        if not makcu_controller.is_connected():
            return False
        if dx == 0 and dy == 0:
            return False

        def ease_out_quad(t):
            return t * (2 - t)

        # FIX 4: Snapshot controller under the lock; verify identity each step.
        with makcu_controller.connection_lock:
            mck = makcu_controller.controller
        if mck is None:
            return False

        step_delay = duration / steps

        # FIX 5: signal that a spray is in progress
        makcu_controller._spray_active.set()

        try:
            acc_x = 0.0
            acc_y = 0.0
            for i in range(steps):
                if interrupt_on_lmb_release and not makcu_controller.button_states.get("LMB", False):
                    return False

                t     = (i + 1) / steps
                eased = ease_out_quad(t)
                tx    = dx * eased
                ty    = dy * eased
                mx    = round(tx - acc_x)
                my    = round(ty - acc_y)
                acc_x += mx
                acc_y += my
                if mx or my:
                    with makcu_controller.command_lock:
                        # FIX 4: abort if controller was swapped by a reconnect
                        if makcu_controller.controller is not mck:
                            return False
                        mck.move(mx, my)
                time.sleep(step_delay)
            return True

        except Exception as e:
            print(f"[MAKCU] Smooth move error: {e}")
            with makcu_controller.connection_lock:
                makcu_controller.is_connected_flag = False
                makcu_controller.controller = None  # FIX 3
            makcu_controller._clear_button_states()  # FIX 1
            return False

        finally:
            # FIX 5: always clear the spray flag
            makcu_controller._spray_active.clear()

    @staticmethod
    def get_button_state(button_name: str):
        return makcu_controller.button_states.get(button_name, False)

    @staticmethod
    def disconnect():
        with makcu_controller.connection_lock:
            if makcu_controller.controller:
                try:
                    makcu_controller.controller.disconnect()
                except Exception:
                    pass
                makcu_controller.controller = None
                makcu_controller.is_connected_flag = False
        makcu_controller._clear_button_states()  # FIX 1
        print("[MAKCU] Disconnected")
'''

# -----------------------------------------------------------------------------
# 2. main.py -- insert await _save_async() into save_pattern
# -----------------------------------------------------------------------------

MAIN_OLD = '    return {"saved": True}'

# We only want to patch the save_pattern function, not any other return.
# Anchor on the line that precedes it to make the match unique.
MAIN_SEARCH = '''\
    if state.loaded_script in (full_name, weapon):
        state.load_script(weapon, game)
    return {"saved": True}'''

MAIN_REPLACE = '''\
    if state.loaded_script in (full_name, weapon):
        state.load_script(weapon, game)
    await _save_async()   # FIX 7: persist config so loaded_script survives restart
    return {"saved": True}'''

# -----------------------------------------------------------------------------
# 3. static/index.html -- fix WebSocket ping interval leak
# -----------------------------------------------------------------------------

# Old: single let ws; declaration
HTML_OLD_DECL   = "let ws;"
HTML_NEW_DECL   = "let ws;let _wsPingInterval;"  # FIX 6

# Old: bare setInterval inside ws.onopen
HTML_OLD_INTERVAL = "setInterval(()=>{if(ws.readyState===1)ws.send('ping');},10000);"
HTML_NEW_INTERVAL = "clearInterval(_wsPingInterval);_wsPingInterval=setInterval(()=>{if(ws.readyState===1)ws.send('ping');},10000);"  # FIX 6

# -----------------------------------------------------------------------------
# Apply patches
# -----------------------------------------------------------------------------

def apply():
    ok = True

    # -- Validate paths --------------------------------------------------------
    for p in (MAKCU_PATH, MAIN_PATH, HTML_PATH):
        if not check(p):
            ok = False
    if not ok:
        print("\n[ERROR] Some files were not found. Make sure you run this script")
        print("        from the root of your Cearum-Web repo:\n")
        print("        cd /path/to/Cearum-Web")
        print("        python3 apply_patches.py\n")
        for e in errors:
            print(f"  !! {e}")
        sys.exit(1)

    # -- Patch 1: makcu.py (full replace) -------------------------------------
    print("\n[ 1/3 ] Patching mouse/makcu.py ...")
    backup(MAKCU_PATH)
    with open(MAKCU_PATH, "w", encoding="utf-8") as f:
        f.write(MAKCU_CONTENT)
    print("  OK Replaced with corrected version (Fixes 1-5, 9)")

    # -- Patch 2: main.py ------------------------------------------------------
    print("\n[ 2/3 ] Patching main.py ...")
    backup(MAIN_PATH)
    with open(MAIN_PATH, "r", encoding="utf-8") as f:
        src = f.read()

    if MAIN_SEARCH not in src:
        print("  !! Could not find the target block in main.py -- already patched?")
        print("     Skipping main.py patch.")
    elif "await _save_async()   # FIX 7" in src:
        print("  -- Fix 7 already present -- skipping.")
    else:
        src = src.replace(MAIN_SEARCH, MAIN_REPLACE, 1)
        with open(MAIN_PATH, "w", encoding="utf-8") as f:
            f.write(src)
        print("  OK Added await _save_async() to save_pattern() (Fix 7)")

    # -- Patch 3: index.html ---------------------------------------------------
    print("\n[ 3/3 ] Patching static/index.html ...")
    backup(HTML_PATH)
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        src = f.read()

    changed = False

    if "_wsPingInterval" in src:
        print("  -- Fix 6 already present -- skipping.")
    else:
        if HTML_OLD_DECL not in src:
            print("  !! Could not find 'let ws;' declaration in index.html -- skipping declaration patch.")
        else:
            src = src.replace(HTML_OLD_DECL, HTML_NEW_DECL, 1)
            changed = True
            print("  OK Added _wsPingInterval declaration (Fix 6)")

        if HTML_OLD_INTERVAL not in src:
            print("  !! Could not find setInterval ping line in index.html -- skipping interval patch.")
        else:
            src = src.replace(HTML_OLD_INTERVAL, HTML_NEW_INTERVAL, 1)
            changed = True
            print("  OK Added clearInterval() guard before setInterval (Fix 6)")

        if changed:
            with open(HTML_PATH, "w", encoding="utf-8") as f:
                f.write(src)

    # -- Done ------------------------------------------------------------------
    print("\n" + "="*54)
    print("  All patches applied.")
    print("  Restart the service to pick up the changes:\n")
    print("    sudo systemctl restart cearum-web")
    print("\n  Check logs with:")
    print("    sudo journalctl -u cearum-web -f")
    print("="*54 + "\n")

if __name__ == "__main__":
    apply()
