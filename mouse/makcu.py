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
    _watchdog_started = False  # Ensures only one watchdog thread runs

    @staticmethod
    def is_connected():
        with makcu_controller.connection_lock:
            return (
                makcu_controller.is_connected_flag
                and makcu_controller.controller is not None
            )

    @staticmethod
    def _watchdog():
        """
        Background daemon thread started once on first successful connect().
        Every 8 seconds it pings the device with a zero-movement command.
        On failure it marks the device disconnected, then keeps retrying
        connect() every 8 seconds until the MAKCU is plugged back in.
        """
        INTERVAL = 8  # seconds — safe, will never stress the device
        while True:
            time.sleep(INTERVAL)

            # ── Phase 1: device is connected — ping it ────────────────
            with makcu_controller.connection_lock:
                connected = makcu_controller.is_connected_flag and makcu_controller.controller is not None
                ctrl = makcu_controller.controller if connected else None

            if connected:
                try:
                    with makcu_controller.command_lock:
                        ctrl.move(0, 0)  # zero-move: no-op for the cursor, exercises the USB handle
                except Exception as e:
                    print(f"[MAKCU] Watchdog detected disconnect: {e}")
                    with makcu_controller.connection_lock:
                        makcu_controller.is_connected_flag = False
                        makcu_controller.controller = None

            # ── Phase 2: device is gone — attempt reconnect ───────────
            else:
                print("[MAKCU] Watchdog attempting reconnect…")
                result = makcu_controller._do_connect()
                if result is not None:
                    print("[MAKCU] Watchdog reconnected successfully")
                # If it failed, the loop sleeps INTERVAL and tries again

    @staticmethod
    def _do_connect():
        """
        Core connection logic shared by connect() and the watchdog.
        Returns the controller on success, None on failure.
        """
        try:
            controller = create_controller(debug=False, auto_reconnect=True)

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
                makcu_controller.controller = None
            return None

    @staticmethod
    def connect():
        with makcu_controller.connection_lock:
            if makcu_controller.controller is not None:
                return makcu_controller.controller

        result = makcu_controller._do_connect()

        # Start the watchdog once on first successful connection
        if result is not None and not makcu_controller._watchdog_started:
            makcu_controller._watchdog_started = True
            threading.Thread(target=makcu_controller._watchdog, daemon=True, name="makcu-watchdog").start()
            print("[MAKCU] Watchdog started (8 s interval)")

        return result

    @staticmethod
    def StartButtonListener():
        makcu_controller.connect()

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
            makcu_controller.is_connected_flag = False
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
            makcu_controller.is_connected_flag = False
            return False

    @staticmethod
    def move_mouse_smoothly(dx, dy, steps=20, duration=0.05, interrupt_on_lmb_release=False):
        if not makcu_controller.is_connected():
            return False
        if dx == 0 and dy == 0:
            return False

        def ease_out_quad(t):
            return t * (2 - t)

        mck = makcu_controller.controller
        step_delay = duration / steps

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
                        mck.move(mx, my)
                time.sleep(step_delay)
            return True
        except Exception as e:
            print(f"[MAKCU] Smooth move error: {e}")
            makcu_controller.is_connected_flag = False
            return False

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
