import time
import threading
from makcu import create_controller, MouseButton


# How long to wait for command_lock before assuming the device is hung.
# 3 s is generous for a normal HID write (should complete in <10 ms).
COMMAND_TIMEOUT = 3.0

# How often the watchdog checks the device when nothing else is using it.
# 30 s is intentionally relaxed — the lock-timeout mechanism handles hung
# devices far faster than a watchdog ping ever could.
WATCHDOG_INTERVAL = 30

# How long to wait between reconnect attempts when the device is absent.
RECONNECT_INTERVAL = 5


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
    _watchdog_thread  = None
    _spray_active     = threading.Event()

    @staticmethod
    def _clear_button_states():
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

            if makcu_controller._spray_active.is_set():
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
            controller = create_controller(debug=False, auto_reconnect=False)

            def on_button_event(button, pressed):
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

        if not makcu_controller._acquire_command_lock():
            return False
        try:
            # v3.7 firmware intercepts programmatic button presses when button
            # monitoring is active — pause monitoring for the click duration.
            mck.enable_button_monitoring(False)
            mck.press(button)
            time.sleep(0.03)
            mck.release(button)
            mck.enable_button_monitoring(True)
            return True
        except Exception as e:
            print(f"[MAKCU] Click error: {e}")
            with makcu_controller.connection_lock:
                makcu_controller.is_connected_flag = False
                makcu_controller.controller = None
            makcu_controller._clear_button_states()
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
                if interrupt_on_lmb_release and not makcu_controller.button_states.get("LMB", False):
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
        return makcu_controller.button_states.get(button_name, False)

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
