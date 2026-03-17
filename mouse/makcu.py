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

    @staticmethod
    def _watchdog():
        INTERVAL = 8
        while True:
            time.sleep(INTERVAL)
            with makcu_controller.connection_lock:
                connected = (
                    makcu_controller.is_connected_flag
                    and makcu_controller.controller is not None
                )
                ctrl = makcu_controller.controller if connected else None
            if connected:
                if makcu_controller._spray_active.is_set():
                    continue
                try:
                    with makcu_controller.command_lock:
                        ctrl.move(0, 0)
                except Exception as e:
                    print(f"[MAKCU] Watchdog detected disconnect: {e}")
                    with makcu_controller.connection_lock:
                        makcu_controller.is_connected_flag = False
                        makcu_controller.controller = None
                    makcu_controller._clear_button_states()
            else:
                print("[MAKCU] Watchdog attempting reconnect...")
                result = makcu_controller._do_connect()
                if result is not None:
                    print("[MAKCU] Watchdog reconnected successfully")

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
        # Always start the watchdog so it can reconnect even if initial
        # connect failed (e.g. MAKCU plugged in after app starts).
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

    @staticmethod
    def click_button(button_name):
        if not makcu_controller.is_connected():
            return False
        with makcu_controller.connection_lock:
            mck = makcu_controller.controller
        if mck is None:
            return False
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
                makcu_controller.controller = None
            makcu_controller._clear_button_states()
            return False

    @staticmethod
    def simple_move_mouse(x, y):
        if not makcu_controller.is_connected():
            return False
        with makcu_controller.connection_lock:
            mck = makcu_controller.controller
        if mck is None:
            return False
        try:
            with makcu_controller.command_lock:
                mck.move(x, y)
            return True
        except Exception as e:
            print(f"[MAKCU] Move error: {e}")
            with makcu_controller.connection_lock:
                makcu_controller.is_connected_flag = False
                makcu_controller.controller = None
            makcu_controller._clear_button_states()
            return False

    @staticmethod
    def move_mouse_smoothly(dx, dy, steps=20, duration=0.05, interrupt_on_lmb_release=False):
        if not makcu_controller.is_connected():
            return False
        if dx == 0 and dy == 0:
            return False

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
                    with makcu_controller.command_lock:
                        if makcu_controller.controller is not mck:
                            return False
                        mck.move(mx, my)
                # Check AFTER sending this step's movement so that at least
                # one micro-move always fires even on the very first step.
                # Checking before step 0 could abort with zero movement when
                # there is a brief race between the outer LMB read and the
                # MAKCU button-callback updating button_states.
                if interrupt_on_lmb_release and not makcu_controller.button_states.get("LMB", False):
                    return False
                time.sleep(step_delay)
            return True
        except Exception as e:
            print(f"[MAKCU] Smooth move error: {e}")
            with makcu_controller.connection_lock:
                makcu_controller.is_connected_flag = False
                makcu_controller.controller = None
            makcu_controller._clear_button_states()
            return False
        finally:
            makcu_controller._spray_active.clear()

    @staticmethod
    def get_button_state(button_name):
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
        makcu_controller._clear_button_states()
        print("[MAKCU] Disconnected")
