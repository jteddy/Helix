import time
import threading
from concurrent.futures import ThreadPoolExecutor
from mouse.makcu import makcu_controller
from state import AppState


# FIX: A single-worker executor caps concurrency to one pending click at a time.
# Previously, every flashlight trigger spawned a new daemon thread. Under normal
# operation the cooldown prevents rapid re-triggers, but using an executor makes
# the limit explicit and avoids any possibility of thread accumulation.
_click_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="flashlight")


class flashlight:

    @staticmethod
    def _delayed_click(keybind: str, delay: float):
        time.sleep(delay)
        makcu_controller.click_button(keybind)

    @staticmethod
    def run_flashlight(state: AppState):
        """
        Mirrors original behaviour exactly:
        - Master switch: flashlight_enabled must be True
        - Recoil must also be enabled (ties flashlight to the recoil toggle)
        - Hold threshold prevents short UI clicks from triggering
        - Cooldown prevents rapid re-triggers
        - Click dispatched on a capped executor thread (max 1 pending)
        """
        lmb_was_pressed     = False
        lmb_press_time      = 0.0
        cooldown_until      = 0.0
        threshold_triggered = False

        while True:
            if not state.get_is_flashlight_enabled():
                lmb_was_pressed     = False
                threshold_triggered = False
                time.sleep(0.02)
                continue

            if not state.get_is_enabled():
                lmb_was_pressed     = False
                threshold_triggered = False
                time.sleep(0.02)
                continue

            keybind = state.get_flashlight_keybind()
            if keybind == "NONE":
                lmb_was_pressed     = False
                threshold_triggered = False
                time.sleep(0.02)
                continue

            lmb_pressed = makcu_controller.get_button_state("LMB")
            now         = time.monotonic()

            # Rising edge
            if lmb_pressed and not lmb_was_pressed:
                lmb_press_time      = now
                threshold_triggered = False

            # While held — check threshold
            if lmb_pressed and not threshold_triggered:
                if (now - lmb_press_time) >= state.get_hold_threshold():
                    threshold_triggered = True
                    if now >= cooldown_until:
                        cooldown_until = now + state.get_cooldown_seconds()
                        pre_fire = state.get_pre_fire_delay()
                        # FIX: submit to bounded executor instead of spawning a raw thread
                        _click_executor.submit(flashlight._delayed_click, keybind, pre_fire)

            # Falling edge
            if not lmb_pressed and lmb_was_pressed:
                threshold_triggered = False

            lmb_was_pressed = lmb_pressed
            time.sleep(0.005)
