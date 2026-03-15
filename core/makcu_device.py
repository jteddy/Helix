"""
core/makcu_device.py
--------------------
Thin wrapper around the makcu library.

Handles:
  - Connection and auto-reconnection
  - Button state tracking via callback
  - Mouse movement (smooth and instant)
  - Thread-safe command locking

Cross-platform: works on Windows and Linux.
On Linux, ensure your user is in the dialout group:
    sudo usermod -a -G dialout $USER
    (log out and back in after)

Usage:
    from core.makcu_device import device

    device.connect()

    if device.is_connected():
        device.move(0, 15)
        device.get_button("LMB")  # True/False
"""

import threading
import time
from core.state import state

try:
    from makcu import create_controller, MouseButton
    MAKCU_AVAILABLE = True
except ImportError:
    MAKCU_AVAILABLE = False
    print("[MAKCU] Warning: makcu library not installed. Run: pip install makcu")


class MakcuDevice:

    def __init__(self):
        self._controller   = None
        self._conn_lock    = threading.Lock()
        self._cmd_lock     = threading.Lock()
        self._button_states = {
            "LMB": False,
            "RMB": False,
            "MMB": False,
            "M4":  False,
            "M5":  False,
        }

    # ── Connection ────────────────────────────────────────────────────────────

    def connect(self) -> bool:
        """
        Connect to the MAKCU device. Returns True on success.
        Safe to call multiple times — will not reconnect if already connected.
        """
        if not MAKCU_AVAILABLE:
            print("[MAKCU] Library not available — running in simulation mode.")
            return False

        with self._conn_lock:
            if self._controller is not None:
                return True

        try:
            controller = create_controller(
                auto_reconnect=True,
                debug=False
            )

            # Button state tracking via callback
            def on_button_event(button: MouseButton, pressed: bool):
                mapping = {
                    MouseButton.LEFT:   "LMB",
                    MouseButton.RIGHT:  "RMB",
                    MouseButton.MIDDLE: "MMB",
                    MouseButton.MOUSE4: "M4",
                    MouseButton.MOUSE5: "M5",
                }
                name = mapping.get(button)
                if name:
                    self._button_states[name] = pressed

            controller.set_button_callback(on_button_event)
            controller.enable_button_monitoring(True)

            with self._conn_lock:
                self._controller = controller

            with state.lock:
                state.makcu_connected = True

            print("[MAKCU] Connected.")
            return True

        except Exception as e:
            print(f"[MAKCU] Connection failed: {e}")
            with state.lock:
                state.makcu_connected = False
            return False

    def disconnect(self):
        with self._conn_lock:
            if self._controller:
                try:
                    self._controller.disconnect()
                except Exception:
                    pass
                self._controller = None
        with state.lock:
            state.makcu_connected = False
        print("[MAKCU] Disconnected.")

    def is_connected(self) -> bool:
        with self._conn_lock:
            return self._controller is not None

    def reconnect_loop(self, interval: float = 3.0):
        """
        Background thread that keeps trying to reconnect if the device
        is unplugged. Call once at startup.
        """
        def _loop():
            while True:
                if not self.is_connected():
                    print("[MAKCU] Attempting reconnect...")
                    self.connect()
                time.sleep(interval)

        t = threading.Thread(target=_loop, daemon=True)
        t.start()

    # ── Button state ──────────────────────────────────────────────────────────

    def get_button(self, name: str) -> bool:
        """Returns True if the named button is currently held."""
        return self._button_states.get(name, False)

    # ── Mouse movement ────────────────────────────────────────────────────────

    def move(self, x: float, y: float) -> bool:
        """Instant mouse move. Returns False if not connected."""
        if not self.is_connected():
            return False
        rx, ry = round(x), round(y)
        if rx == 0 and ry == 0:
            return True
        try:
            with self._cmd_lock:
                self._controller.move(rx, ry)
            return True
        except Exception as e:
            print(f"[MAKCU] Move error: {e}")
            self._mark_disconnected()
            return False

    def move_smooth(self, dx: float, dy: float,
                    steps: int = 20, duration: float = 0.05,
                    interrupt_on_lmb_release: bool = False) -> bool:
        """
        Smooth eased mouse movement over multiple steps.
        Mirrors Cearum's move_mouse_smoothly logic exactly.
        Returns True if the full movement completed, False if interrupted.
        """
        if not self.is_connected():
            return False
        if dx == 0 and dy == 0:
            return False

        def ease_out_quad(t):
            return t * (2 - t)

        step_delay    = duration / steps
        accumulated_x = 0.0
        accumulated_y = 0.0

        try:
            for i in range(steps):
                if interrupt_on_lmb_release and not self._button_states.get("LMB", False):
                    return False

                t      = (i + 1) / steps
                eased  = ease_out_quad(t)
                target_x = dx * eased
                target_y = dy * eased

                delta_x = target_x - accumulated_x
                delta_y = target_y - accumulated_y
                move_x  = round(delta_x)
                move_y  = round(delta_y)

                accumulated_x += move_x
                accumulated_y += move_y

                if move_x or move_y:
                    with self._cmd_lock:
                        self._controller.move(move_x, move_y)

                time.sleep(step_delay)

            return True

        except Exception as e:
            print(f"[MAKCU] Smooth move error: {e}")
            self._mark_disconnected()
            return False

    # ── Internal ──────────────────────────────────────────────────────────────

    def _mark_disconnected(self):
        with self._conn_lock:
            self._controller = None
        with state.lock:
            state.makcu_connected = False


# ── Singleton ─────────────────────────────────────────────────────────────────
device = MakcuDevice()
