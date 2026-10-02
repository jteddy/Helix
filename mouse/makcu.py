import re
import time
import threading
from collections import deque

import serial
from makcu import create_controller, MouseButton

# The library's listener thread consumes the serial port, so the only place to see the
# raw bytes is a wrapper around the serial class's read(). It feeds the binary frame
# decoder, and keeps the latest non-text bytes (anything but printable ASCII and CR/LF,
# i.e. button-stream or binary frames) with context for the Button Monitor.
_rx_events = deque(maxlen=30)
_rx_nontext = [0]


def _install_rx_tee():
    cls = serial.Serial
    orig = cls.read
    if getattr(orig, "_helix_tee", False):
        return

    def read(self, size=1):
        data = orig(self, size)
        if data:
            try:
                makcu_controller._decode_frames(data)
            except Exception as e:
                print(f"[MAKCU] Frame decode error: {e}")
            for i, b in enumerate(data):
                if (b < 32 and b != 10 and b != 13) or b > 126:
                    _rx_nontext[0] += 1
                    now = time.monotonic()
                    if not _rx_events or now - _rx_events[-1][0] > 0.05:  # one entry per frame
                        _rx_events.append((now, bytes(data[max(0, i - 6): i + 10])))
        return data

    read._helix_tee = True
    cls.read = read


try:
    _install_rx_tee()
except Exception as e:  # diagnostics only; never block startup
    print(f"[MAKCU] RX capture unavailable: {e}")


# The makcu library switches the link to this rate during connect (legacy
# baud-change frame + host side); verify_link() confirms it took effect.
TARGET_BAUD = 4000000

# Programmatic click: hold time, and km.click's button numbers (the V3 reference
# numbers buttons 1=left 2=right 3=middle 4=side1 5=side2).
CLICK_HOLD_MS = 30
CLICK_INDEX = {"LMB": 1, "RMB": 2, "MMB": 3, "M4": 4, "M5": 5}

# How long to wait for command_lock before assuming the device is hung.
# 3 s is generous for a normal HID write (should complete in <10 ms).
COMMAND_TIMEOUT = 3.0

# How often the watchdog checks the device when nothing else is using it.
# 30 s is intentionally relaxed — the lock-timeout mechanism handles hung
# devices far faster than a watchdog ping ever could.
WATCHDOG_INTERVAL = 30

# How long to wait between reconnect attempts when the device is absent.
RECONNECT_INTERVAL = 5


_BTN_NAMES = ("LMB", "RMB", "MMB", "M4", "M5")          # 0x53 mouse event ids 0..4
_ENUM_NAME = {
    MouseButton.LEFT: "LMB", MouseButton.RIGHT: "RMB", MouseButton.MIDDLE: "MMB",
    MouseButton.MOUSE4: "M4", MouseButton.MOUSE5: "M5",
}


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
    _button_lock      = threading.Lock()
    is_connected_flag = False
    _watchdog_thread  = None
    _spray_active     = threading.Event()
    _recording        = threading.Event()   # pattern recorder is polling getpos
    _clicking_button  = None          # MouseButton being programmatically clicked
    _native_click     = False         # True once the firmware is known to support km.click
    _framed           = False         # button events arrive as binary 0x53 frames
    _frame_buf        = bytearray()   # partial frame carried between reads
    _last_reenable    = 0.0
    _last_mask        = 0             # previous button mask from the text stream
    lib_mask_calls    = 0             # times the library's parser handed us a mask byte
    lib_error         = None
    button_events     = {n: 0 for n in _BTN_NAMES}      # press/release events Helix processed
    button_last       = {n: None for n in _BTN_NAMES}   # monotonic time of the last change
    overflow_count    = 0
    last_overflow     = None
    _overflow_times   = deque(maxlen=10)
    _waiter           = None          # (regex, Event, matches) for the pending query()
    _info_lock        = threading.Lock()
    device_info       = {"firmware": None, "baud": None, "baud_ok": None}

    @staticmethod
    def _clear_button_states():
        makcu_controller._last_mask = 0
        with makcu_controller._button_lock:
            for k in makcu_controller.button_states:
                makcu_controller.button_states[k] = False

    @staticmethod
    def is_connected():
        with makcu_controller.connection_lock:
            return (
                makcu_controller.is_connected_flag
                and makcu_controller.controller is not None
            )

    # ── Lock helper ───────────────────────────────────────────────────────────

    @staticmethod
    def _acquire_command_lock(timeout: float = COMMAND_TIMEOUT) -> bool:
        """Try to acquire command_lock within *timeout* seconds.

        Returns True on success.  On timeout the device is assumed to be in a
        hung state: is_connected_flag is cleared, button states are reset, and
        False is returned so the caller can bail out cleanly.
        """
        acquired = makcu_controller.command_lock.acquire(timeout=timeout)
        if not acquired:
            print(
                f"[MAKCU] command_lock timeout after {timeout}s "
                "— device likely hung, marking disconnected"
            )
            with makcu_controller.connection_lock:
                makcu_controller.is_connected_flag = False
                makcu_controller.controller = None
            makcu_controller._clear_button_states()
        return acquired

    # ── Watchdog ──────────────────────────────────────────────────────────────

    @staticmethod
    def _watchdog():
        """Background thread: reconnects when the device is absent, and pings
        every WATCHDOG_INTERVAL seconds when connected to detect silent USB
        drops.

        When disconnected, retries _do_connect() every RECONNECT_INTERVAL
        seconds so that the device recovers automatically after a USB event
        (e.g. game PC power cycle) without requiring a server restart.

        Skips pings while a spray is active to avoid competing for
        command_lock mid-burst.  The lock-timeout mechanism still protects
        against truly hung devices in all other callers.
        """
        while True:
            with makcu_controller.connection_lock:
                connected = (
                    makcu_controller.is_connected_flag
                    and makcu_controller.controller is not None
                )

            if not connected:
                time.sleep(RECONNECT_INTERVAL)
                # Guard: another code path may have reconnected while we slept.
                with makcu_controller.connection_lock:
                    if makcu_controller.controller is not None:
                        continue
                if makcu_controller._do_connect() is not None:
                    print("[MAKCU] Reconnected")
                continue

            # ── Connected: periodic health ping ──────────────────────────────
            time.sleep(WATCHDOG_INTERVAL)

            # Re-read — state may have changed while sleeping.
            with makcu_controller.connection_lock:
                connected = (
                    makcu_controller.is_connected_flag
                    and makcu_controller.controller is not None
                )
                ctrl = makcu_controller.controller if connected else None

            if not connected:
                continue

            if (
                makcu_controller._spray_active.is_set()
                or makcu_controller._recording.is_set()
                or makcu_controller._clicking_button is not None
                or makcu_controller.button_states["LMB"]   # a re-enable restarts the stream's baseline
            ):
                continue

            if not makcu_controller._acquire_command_lock():
                # Timeout — device marked disconnected inside helper.
                continue
            try:
                ctrl.move(0, 0)
                ctrl.enable_button_monitoring(True)
            except Exception as e:
                print(f"[MAKCU] Watchdog ping failed: {e}")
                with makcu_controller.connection_lock:
                    makcu_controller.is_connected_flag = False
                    makcu_controller.controller = None
                makcu_controller._clear_button_states()
            finally:
                makcu_controller.command_lock.release()

    # ── Connection ────────────────────────────────────────────────────────────

    @staticmethod
    def _do_connect():
        try:
            makcu_controller._framed = False
            makcu_controller._last_mask = 0
            makcu_controller._frame_buf.clear()
            controller = create_controller(debug=False, auto_reconnect=False)

            def on_button_event(button, pressed):
                # Once binary 0x53 frames are seen they are decoded by _decode_frames;
                # the library parses those bytes as masks and reports garbage.
                if makcu_controller._framed:
                    return
                name = _ENUM_NAME.get(button)
                if name:
                    makcu_controller._set_button(name, pressed)

            controller.set_button_callback(on_button_event)
            makcu_controller._install_line_hook(controller)
            makcu_controller._install_mask_handler(controller)
            controller.enable_button_monitoring(True)

            with makcu_controller.connection_lock:
                makcu_controller.controller = controller
                makcu_controller.is_connected_flag = True

            makcu_controller._native_click = False
            makcu_controller._set_info(firmware=None, baud="checking…", baud_ok=None)
            threading.Thread(
                target=makcu_controller.verify_link, args=(controller,),
                daemon=True, name="makcu-verify",
            ).start()

            return controller

        except Exception as e:
            print(f"[MAKCU] Connection error: {e}")
            with makcu_controller.connection_lock:
                makcu_controller.is_connected_flag = False
                makcu_controller.controller = None
            makcu_controller._clear_button_states()
            return None

    @staticmethod
    def connect():
        with makcu_controller.connection_lock:
            if makcu_controller.controller is not None:
                return makcu_controller.controller
        result = makcu_controller._do_connect()
        # Start watchdog even if initial connect failed — device may be
        # plugged in after the server starts.
        t = makcu_controller._watchdog_thread
        if t is None or not t.is_alive():
            new_t = threading.Thread(
                target=makcu_controller._watchdog,
                daemon=True,
                name="makcu-watchdog",
            )
            new_t.start()
            makcu_controller._watchdog_thread = new_t
            print(f"[MAKCU] Watchdog started ({WATCHDOG_INTERVAL}s interval)")
        return result

    @staticmethod
    def StartButtonListener():
        makcu_controller.connect()

    # ── Button click ──────────────────────────────────────────────────────────

    @staticmethod
    def click_button(button_name):
        if not makcu_controller.is_connected():
            return False
        with makcu_controller.connection_lock:
            mck = makcu_controller.controller
        if mck is None:
            return False
        button_map = {
            "LMB": MouseButton.LEFT,
            "RMB": MouseButton.RIGHT,
            "MMB": MouseButton.MIDDLE,
            "M4":  MouseButton.MOUSE4,
            "M5":  MouseButton.MOUSE5,
        }
        button = button_map.get(button_name)
        if button is None:
            return False

        native = makcu_controller._native_click
        if not makcu_controller._acquire_command_lock():
            return False
        try:
            # Keep monitoring ON throughout the click.  v3.7 firmware
            # re-reports programmatic presses as button events, but the
            # _clicking_button callback filter silently drops them so they
            # never corrupt button_states or trip the toggle keybind.
            # NOT toggling monitoring avoids two problems:
            #   1. A monitoring gap that loses physical LMB release events
            #   2. Rapid enable/disable cycling that can desync the firmware
            with makcu_controller._button_lock:
                makcu_controller._clicking_button = button
            if native:
                ser = mck.transport.serial
                ser.write(f"km.click({CLICK_INDEX[button_name]},1,{CLICK_HOLD_MS})\r\n".encode("ascii"))
                ser.flush()
            else:
                mck.press(button)
        except Exception as e:
            print(f"[MAKCU] Click error: {e}")
            makcu_controller._mark_disconnected()
            with makcu_controller._button_lock:
                makcu_controller._clicking_button = None
            return False
        finally:
            makcu_controller.command_lock.release()

        # The lock is deliberately not held while the button is down: recoil
        # moves would otherwise stall for the whole hold.
        try:
            time.sleep(CLICK_HOLD_MS / 1000.0)
            if not native and not makcu_controller._release_button(mck, button):
                return False
            # Let pending firmware events drain while the filter is still
            # active.  5 ms is well above typical USB HID latency (~1-2 ms).
            time.sleep(0.005)
            return True
        finally:
            with makcu_controller._button_lock:
                makcu_controller._clicking_button = None

    @staticmethod
    def _release_button(mck, button):
        if not makcu_controller._acquire_command_lock():
            return False
        try:
            if makcu_controller.controller is not mck:
                return False  # replaced by a reconnect while the button was down
            mck.release(button)
            return True
        except Exception as e:
            print(f"[MAKCU] Click release error: {e}")
            makcu_controller._mark_disconnected()
            return False
        finally:
            makcu_controller.command_lock.release()

    # ── Simple move ───────────────────────────────────────────────────────────

    @staticmethod
    def simple_move_mouse(x, y):
        if not makcu_controller.is_connected():
            return False
        with makcu_controller.connection_lock:
            mck = makcu_controller.controller
        if mck is None:
            return False

        if not makcu_controller._acquire_command_lock():
            return False
        try:
            mck.move(x, y)
            return True
        except Exception as e:
            print(f"[MAKCU] Move error: {e}")
            with makcu_controller.connection_lock:
                makcu_controller.is_connected_flag = False
                makcu_controller.controller = None
            makcu_controller._clear_button_states()
            return False
        finally:
            makcu_controller.command_lock.release()

    # ── Smooth move ───────────────────────────────────────────────────────────

    @staticmethod
    def move_mouse_smoothly(dx, dy, steps=20, duration=0.05, interrupt_on_lmb_release=False):
        if not makcu_controller.is_connected():
            return False
        if dx == 0 and dy == 0:
            # No movement needed — treat as completed, not interrupted.
            return True

        def ease_out_quad(t):
            return t * (2 - t)

        with makcu_controller.connection_lock:
            mck = makcu_controller.controller
        if mck is None:
            return False

        step_delay = duration / steps
        makcu_controller._spray_active.set()

        try:
            acc_x = 0.0
            acc_y = 0.0
            for i in range(steps):
                t     = (i + 1) / steps
                eased = ease_out_quad(t)
                tx    = dx * eased
                ty    = dy * eased
                mx    = round(tx - acc_x)
                my    = round(ty - acc_y)
                acc_x += mx
                acc_y += my

                if mx or my:
                    if not makcu_controller._acquire_command_lock():
                        # Device hung — bail out immediately.
                        return False
                    try:
                        if makcu_controller.controller is not mck:
                            # Controller was replaced under us (reconnect).
                            return False
                        mck.move(mx, my)
                    except Exception as e:
                        print(f"[MAKCU] Smooth move error: {e}")
                        with makcu_controller.connection_lock:
                            makcu_controller.is_connected_flag = False
                            makcu_controller.controller = None
                        makcu_controller._clear_button_states()
                        return False
                    finally:
                        makcu_controller.command_lock.release()

                # Check AFTER sending this step's movement so that at least
                # one micro-move always fires even on the very first step.
                if interrupt_on_lmb_release and not makcu_controller.get_button_state("LMB"):
                    return False

                time.sleep(step_delay)

            return True

        except Exception as e:
            print(f"[MAKCU] Smooth move unexpected error: {e}")
            with makcu_controller.connection_lock:
                makcu_controller.is_connected_flag = False
                makcu_controller.controller = None
            makcu_controller._clear_button_states()
            return False
        finally:
            makcu_controller._spray_active.clear()

    # ── Button state query ────────────────────────────────────────────────────

    @staticmethod
    def get_button_state(button_name):
        with makcu_controller._button_lock:
            return makcu_controller.button_states.get(button_name, False)

    # ── Button events ─────────────────────────────────────────────────────────

    @staticmethod
    def _set_button(name, pressed):
        with makcu_controller._button_lock:
            # Ignore spurious events for a button being clicked
            # programmatically — the firmware re-reports them when
            # monitoring is toggled back on around each HID command.
            if _ENUM_NAME.get(makcu_controller._clicking_button) == name:
                return
            makcu_controller.button_states[name] = pressed
            makcu_controller.button_events[name] += 1
            makcu_controller.button_last[name] = time.monotonic()

    @staticmethod
    def _install_mask_handler(controller):
        """Take over the library's button-mask handler.

        The library's parser recognises mask bytes in the text stream, but its handler prints
        before it fires the callback; if stdout is broken the print raises, the library
        swallows it, and no button event is ever delivered. Our handler needs no I/O."""
        transport = getattr(controller, "transport", None)
        if transport is None or not hasattr(transport, "_handle_button_data"):
            print("[MAKCU] Library mask handler not found — using its callback instead")
            return

        def handle(byte_val):
            makcu_controller.lib_mask_calls += 1
            try:
                makcu_controller._apply_mask(byte_val)
            except Exception as e:
                makcu_controller.lib_error = repr(e)

        transport._handle_button_data = handle

    @staticmethod
    def _apply_mask(mask):
        if makcu_controller._framed:
            return
        changed = mask ^ makcu_controller._last_mask
        makcu_controller._last_mask = mask
        for bit, name in enumerate(_BTN_NAMES):
            if changed & (1 << bit):
                makcu_controller._set_button(name, bool(mask & (1 << bit)))

    @staticmethod
    def _decode_frames(data):
        """Decode binary input-change frames `DE AD LEN:u16 CMD PAYLOAD` out of the raw
        bytes the library is reading. Newer firmware sends the button stream this way
        (`53 kind id state`; kind 1 = mouse, id 0..4 = LMB RMB MMB M4 M5; id/state FF FF
        = overflow). Runs on the library's listener thread, before its own parser."""
        buf = makcu_controller._frame_buf
        buf += data
        while True:
            i = buf.find(b"\xde\xad")
            if i < 0:
                del buf[: len(buf) - (1 if buf.endswith(b"\xde") else 0)]
                return
            del buf[:i]
            if len(buf) < 5:
                return
            length = buf[2] | (buf[3] << 8)
            if length > 16:             # not a real frame
                del buf[:2]
                continue
            total = 5 + length
            if len(buf) < total:
                return
            cmd, payload = buf[4], bytes(buf[5:total])
            del buf[:total]
            if cmd == 0x53 and len(payload) == 3 and payload[0] == 1:
                makcu_controller._on_stream_event(payload[1], payload[2])

    @staticmethod
    def _on_stream_event(bid, state):
        makcu_controller._framed = True
        if bid == 0xFF and state == 0xFF:
            # Overflow: the firmware has disabled the mouse stream and dropped queued
            # changes. Forget cached state and ask for the stream again.
            now = time.monotonic()
            makcu_controller.overflow_count += 1
            makcu_controller.last_overflow = now
            makcu_controller._overflow_times.append(now)
            print("[MAKCU] Button stream overflow — re-enabling")
            makcu_controller._clear_button_states()
            makcu_controller._reenable_stream()
        elif bid < len(_BTN_NAMES) and state in (0, 1):
            makcu_controller._set_button(_BTN_NAMES[bid], bool(state))

    @staticmethod
    def _reenable_stream():
        now = time.monotonic()
        if now - makcu_controller._last_reenable < 0.5:
            return
        if makcu_controller.overflow_loop():
            return  # re-enabling just overflows again; stop thrashing and let the user look
        makcu_controller._last_reenable = now
        # Not from the listener thread: send_text takes locks and writes to the port.
        threading.Thread(
            target=makcu_controller.send_text, args=("km.buttons(1)",), daemon=True
        ).start()

    @staticmethod
    def stream_format():
        return "0x53 frames" if makcu_controller._framed else "text or none seen"

    @staticmethod
    def overflow_loop():
        t = makcu_controller._overflow_times
        return len(t) >= 5 and time.monotonic() - t[-5] < 30

    @staticmethod
    def button_summary():
        now = time.monotonic()
        with makcu_controller._button_lock:
            states = dict(makcu_controller.button_states)
            events = dict(makcu_controller.button_events)
            last = dict(makcu_controller.button_last)
        lo = makcu_controller.last_overflow
        return {
            "states": states,
            "events": events,
            "last_change_age_s": {k: (round(now - v, 1) if v else None) for k, v in last.items()},
            "stream_format": makcu_controller.stream_format(),
            "framed": makcu_controller._framed,
            "overflows": makcu_controller.overflow_count,
            "last_overflow_age_s": round(now - lo, 1) if lo else None,
            "overflow_loop": makcu_controller.overflow_loop(),
            "nontext_bytes": _rx_nontext[0],
            "lib_mask_calls": makcu_controller.lib_mask_calls,
            "lib_error": makcu_controller.lib_error,
            "recent_frames": [
                {"age_s": round(now - t, 2), "hex": makcu_controller._fmt(d)["hex"]}
                for t, d in list(_rx_events)[-10:]
            ],
        }

    @staticmethod
    def reset_button_stats():
        with makcu_controller._button_lock:
            for n in _BTN_NAMES:
                makcu_controller.button_events[n] = 0
                makcu_controller.button_last[n] = None
        makcu_controller.overflow_count = 0
        makcu_controller.last_overflow = None
        makcu_controller._overflow_times.clear()

    @staticmethod
    def probe_buttons():
        """Ask the firmware for the stream switch and each button's state. Returns
        (stream_enabled, {name: 0..3 or None}, note). Skipped while the recorder or a
        spray is using the line."""
        if makcu_controller._recording.is_set() or makcu_controller._spray_active.is_set():
            return None, None, "skipped: recorder or recoil is using the line"
        m = makcu_controller.query(
            "km.buttons()", r"^[>\s]*(?:km\.buttons\()?([01])\)?\s*$", timeout=0.06, retries=1
        )
        enabled = None if m is None else m.group(1) == "1"
        probe = {}
        for name, cmd in (("LMB", "left"), ("RMB", "right"), ("MMB", "middle"), ("M4", "side1"), ("M5", "side2")):
            r = makcu_controller.query(
                f"km.{cmd}()", r"^[>\s]*(?:km\.\w+\()?([0-3])\)?\s*$", timeout=0.05, retries=1
            )
            probe[name] = None if r is None else int(r.group(1))
            if enabled is None and name == "LMB" and r is None:
                return None, None, "firmware did not answer km.buttons() or km.left()"
        return enabled, probe, None

    @staticmethod
    def enable_stream(mode):
        if mode == "binary":
            frame = bytes([0xDE, 0xAD, 2, 0, 0x52, 1, 1])      # INPUT_STREAM SET mouse on
            if not makcu_controller._acquire_command_lock():
                return False, "command lock timeout"
            try:
                with makcu_controller.connection_lock:
                    ctrl = makcu_controller.controller
                if ctrl is None:
                    return False, "not connected"
                ctrl.transport.serial.write(frame)
                ctrl.transport.serial.flush()
            except Exception as e:
                return False, f"write failed: {e}"
            finally:
                makcu_controller.command_lock.release()
            return True, "binary INPUT_STREAM set: " + " ".join(f"{b:02x}" for b in frame)
        m = makcu_controller.query("km.buttons(1)", r"\S", timeout=0.3, retries=1)
        reply = m.string.lstrip("> ").strip() if m else None
        return makcu_controller.is_connected(), f"km.buttons(1) (reply: {reply or 'none'})"

    @staticmethod
    def device_route():
        m = makcu_controller.query("km.device()", r"^[>\s]*(\(.*\)|R:.*)\s*$", timeout=0.2, retries=2)
        return m.group(1) if m else None

    # ── Text queries (replies arrive via the library's line parser) ───────────
    #
    # The library's listener thread owns the serial port and drops any reply
    # we did not register for, so query() hooks its line callback instead of
    # reading the port ourselves.

    @staticmethod
    def _install_line_hook(controller):
        transport = getattr(controller, "transport", None)
        original = getattr(transport, "_process_pending_commands", None)
        if original is None:
            print("[MAKCU] Library line hook unavailable — text queries disabled")
            return

        def hook(content):
            w = makcu_controller._waiter
            if w is not None:
                rx, ev, out = w
                m = rx.search(content)
                if m and not ev.is_set():
                    out.append(m)
                    ev.set()
            return original(content)

        transport._process_pending_commands = hook

    @staticmethod
    def _set_info(**kw):
        with makcu_controller._info_lock:
            makcu_controller.device_info.update(kw)

    @staticmethod
    def _mark_disconnected():
        with makcu_controller.connection_lock:
            makcu_controller.is_connected_flag = False
            makcu_controller.controller = None
        makcu_controller._clear_button_states()

    @staticmethod
    def query(cmd, pattern, timeout=0.3, retries=3):
        """Send a text command and return the first reply line matching
        *pattern* (a regex searched in each line), or None. Retries because a
        stray prompt can garble the first reply line after a burst of setters."""
        rx = re.compile(pattern)
        for _ in range(retries):
            if not makcu_controller._acquire_command_lock():
                return None
            ev, out = threading.Event(), []
            try:
                with makcu_controller.connection_lock:
                    ctrl = makcu_controller.controller
                if ctrl is None:
                    return None
                makcu_controller._waiter = (rx, ev, out)
                try:
                    ser = ctrl.transport.serial
                    ser.write(f"{cmd}\r\n".encode("ascii"))
                    ser.flush()
                except Exception as e:
                    print(f"[MAKCU] Query write error: {e}")
                    makcu_controller._mark_disconnected()
                    return None
                if ev.wait(timeout):
                    return out[0]
            finally:
                makcu_controller._waiter = None
                makcu_controller.command_lock.release()
        return None

    @staticmethod
    def send_text(cmd):
        """Fire-and-forget text command (no reply expected)."""
        if not makcu_controller._acquire_command_lock():
            return False
        try:
            with makcu_controller.connection_lock:
                ctrl = makcu_controller.controller
            if ctrl is None:
                return False
            ctrl.transport.serial.write(f"{cmd}\r\n".encode("ascii"))
            ctrl.transport.serial.flush()
            return True
        except Exception as e:
            print(f"[MAKCU] Send error: {e}")
            makcu_controller._mark_disconnected()
            return False
        finally:
            makcu_controller.command_lock.release()

    @staticmethod
    def get_pos(timeout=0.1):
        """Firmware-tracked pointer position (V3.x and V4.026+), or None."""
        m = makcu_controller.query(
            "km.getpos()", r"getpos\((-?\d+)\s*,\s*(-?\d+)\)", timeout, retries=1
        )
        return (int(m.group(1)), int(m.group(2))) if m else None

    @staticmethod
    def get_screen():
        m = makcu_controller.query("km.screen()", r"screen\((\d+)\s*,\s*(\d+)\)")
        return (int(m.group(1)), int(m.group(2))) if m else None

    @staticmethod
    def set_screen(w, h):
        return makcu_controller.send_text(f"km.screen({int(w)},{int(h)})")

    # ── Link verification ─────────────────────────────────────────────────────

    @staticmethod
    def verify_link(controller):
        """Confirm the serial link really runs at TARGET_BAUD.

        The library never checks that the device accepted the baud switch, so
        a failed switch looks like a healthy connection. Any valid reply at
        the host rate proves the device is at that rate too."""
        time.sleep(0.3)
        try:
            ser = controller.transport.serial
            if ser is not None and ser.baudrate != TARGET_BAUD:
                print(f"[MAKCU] Host baud was {ser.baudrate}, forcing {TARGET_BAUD}")
                ser.baudrate = TARGET_BAUD
        except Exception as e:
            print(f"[MAKCU] Could not check host baud: {e}")

        ver = makcu_controller.query("km.version()", r"MAKCU")
        # Accepts "4000000" and "km.baud(4000000)": the reply form is not documented.
        baud = (
            makcu_controller.query("km.baud()", r"^[>\s]*(?:km\.baud\()?(\d{4,8})\)?\s*$", retries=2)
            if ver else None
        )

        if makcu_controller.controller is not controller:
            return  # reconnected or dropped while probing

        # km.baud() exists only on V4.073+, which implies km.click (V4.026+).
        makcu_controller._native_click = baud is not None
        reply = ver.string.lstrip("> ").strip() if ver else None
        if baud is not None:
            rate = int(baud.group(1))
            ok = rate == TARGET_BAUD
            info = {
                "firmware": f"{reply} (V4.073 or newer)",
                "baud": f"{rate:,} (confirmed by device)" if ok else f"{rate:,} — expected {TARGET_BAUD:,}",
                "baud_ok": ok,
            }
        elif ver is not None:
            info = {
                "firmware": f"{reply} (V3.x or V4 older than V4.073)",
                "baud": f"{TARGET_BAUD:,} (device replies at this rate; firmware can't report baud)",
                "baud_ok": True,
            }
        else:
            info = {
                "firmware": None,
                "baud": "No reply to km.version() — baud could not be confirmed",
                "baud_ok": None,
            }
        makcu_controller._set_info(**info)
        print(f"[MAKCU] Link check: {info['baud']}")

    @staticmethod
    def _fmt(data):
        return {
            "hex": " ".join(f"{b:02x}" for b in data),
            "ascii": "".join(chr(b) if 32 <= b < 127 else "." for b in data),
        }

    @staticmethod
    def rx_nontext():
        """(count of non-text bytes received so far, hex of the latest frame or None)."""
        last = _rx_events[-1][1] if _rx_events else None
        return _rx_nontext[0], (makcu_controller._fmt(last)["hex"] if last else None)

    @staticmethod
    def device_summary():
        if not makcu_controller.is_connected():
            return {"connected": False, "firmware": None, "baud": None, "baud_ok": None}
        with makcu_controller._info_lock:
            return {"connected": True, **makcu_controller.device_info}

    # ── Disconnect ────────────────────────────────────────────────────────────

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
        makcu_controller._clear_button_states()
        print("[MAKCU] Disconnected")
