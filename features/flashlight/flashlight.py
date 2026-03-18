import time
import threading
from concurrent.futures import ThreadPoolExecutor
from mouse.makcu import makcu_controller
from state import AppState


# A single-worker executor caps concurrency to one pending click at a time.
_click_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="flashlight")


def shutdown_executor():
    """Call during app shutdown to cleanly drain the flashlight click executor."""
    _click_executor.shutdown(wait=True)


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
        _dbg_printed        = False  # rate-limit diagnostic prints

        while True:
            fl_on      = state.get_is_flashlight_enabled()
            recoil_on  = state.get_is_enabled()
            keybind    = state.get_flashlight_keybind()

            if not fl_on or not recoil_on or keybind == "NONE":
                if not _dbg_printed:
                    print(f"[Flashlight] Waiting — fl={fl_on} recoil={recoil_on} kb={keybind}")
                    _dbg_printed = True
                lmb_was_pressed     = False
                threshold_triggered = False
                time.sleep(0.02)
                continue

            _dbg_printed = False
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
                        print(f"[Flashlight] Firing {keybind} (pre-fire {pre_fire*1000:.0f}ms)")
                        try:
                            _click_executor.submit(flashlight._delayed_click, keybind, pre_fire)
                        except RuntimeError:
                            pass  # Executor shut down during app exit — ignore
                    else:
                        print(f"[Flashlight] Blocked by cooldown ({cooldown_until - now:.2f}s remaining)")

            # Falling edge
            if not lmb_pressed and lmb_was_pressed:
                threshold_triggered = False

            lmb_was_pressed = lmb_pressed
            time.sleep(0.005)
