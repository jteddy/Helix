from mouse.makcu import makcu_controller
from state import AppState
from menu.games import GAME_BASE_SENSITIVITIES
import time
import random


class recoil:

    @staticmethod
    def jitter(value, max_offset):
        return value + random.uniform(-max_offset, max_offset)

    @staticmethod
    def sens_scalar(state: AppState) -> float:
        scalar_mode = state.get_game_scalar()
        if scalar_mode in GAME_BASE_SENSITIVITIES:
            base = GAME_BASE_SENSITIVITIES[scalar_mode]
            user_sens = state.get_game_sensitivity()
            return base / user_sens if user_sens > 0 else 1.0
        return state.get_recoil_scalar()

    @staticmethod
    def run_recoil(state: AppState):
        shot_count       = 0
        total_y_movement = 0
        lmb_was_pressed  = False
        last_toggle_state = False
        last_cycle_state  = False
        last_toggle_time  = 0.0
        last_cycle_time   = 0.0
        DEBOUNCE = 0.3

        while True:
            now = time.monotonic()

            # ── Toggle keybind (MAKCU button) ─────────────────────────────────
            toggle_key = state.get_toggle_keybind()
            if toggle_key != "NONE":
                toggle_pressed = makcu_controller.get_button_state(toggle_key)
                if toggle_pressed and not last_toggle_state and (now - last_toggle_time) >= DEBOUNCE:
                    state.toggle_recoil()
                    last_toggle_time = now
                last_toggle_state = toggle_pressed

            # ── Cycle keybind (MAKCU button) ──────────────────────────────────
            cycle_key = state.get_cycle_bind()
            if cycle_key != "NONE":
                cycle_pressed = makcu_controller.get_button_state(cycle_key)
                if cycle_pressed and not last_cycle_state and (now - last_cycle_time) >= DEBOUNCE:
                    state.cycle_script()
                    last_cycle_time = now
                last_cycle_state = cycle_pressed

            # ── Recoil disabled ───────────────────────────────────────────────
            if not state.get_is_enabled():
                shot_count       = 0
                total_y_movement = 0
                lmb_was_pressed  = False
                time.sleep(0.05)
                continue

            recoil_pattern = state.vectors
            lmb_pressed    = makcu_controller.get_button_state("LMB")

            # ── LMB released — optionally return crosshair ────────────────────
            if not lmb_pressed and lmb_was_pressed and total_y_movement != 0:
                if state.get_return_crosshair_enabled():
                    makcu_controller.move_mouse_smoothly(0, -total_y_movement, 20, state.get_return_speed())
                total_y_movement = 0
                shot_count       = 0
                lmb_was_pressed  = False
                time.sleep(0.02)
                continue

            if not lmb_pressed:
                shot_count       = 0
                total_y_movement = 0
                lmb_was_pressed  = False
                time.sleep(0.02)
                continue

            # ── LMB just pressed ──────────────────────────────────────────────
            if not lmb_was_pressed:
                shot_count       = 0
                total_y_movement = 0
            lmb_was_pressed = True

            # ── Fire recoil ───────────────────────────────────────────────────
            if recoil_pattern:
                if state.requires_right_button() and not makcu_controller.get_button_state("RMB"):
                    time.sleep(0.02)
                    continue

                if shot_count >= len(recoil_pattern):
                    if state.get_is_recoil_looped():
                        shot_count = 0
                    else:
                        time.sleep(0.02)
                        continue

                x, y, delay = recoil_pattern[shot_count]

                if state.get_is_randomisation_enabled():
                    strength = state.get_randomisation_strength()
                    x = recoil.jitter(x, strength)
                    y = recoil.jitter(y, strength)

                scalar   = recoil.sens_scalar(state)
                actual_x = x * state.get_x_control() * scalar
                actual_y = y * state.get_y_control() * scalar

                start_time    = time.perf_counter()
                move_completed = makcu_controller.move_mouse_smoothly(
                    actual_x, actual_y, interrupt_on_lmb_release=True
                )

                if move_completed:
                    total_y_movement += actual_y

                # ── Poll LMB during inter-shot delay ──────────────────────────
                # If LMB is released at any point during the delay, treat this
                # as a tap-fire: reset shot_count so the next press starts fresh.
                elapsed   = time.perf_counter() - start_time
                remaining = delay - elapsed
                lmb_released_during_delay = False
                if remaining > 0:
                    deadline = time.perf_counter() + remaining
                    while time.perf_counter() < deadline:
                        if not makcu_controller.get_button_state("LMB"):
                            lmb_released_during_delay = True
                            break
                        time.sleep(0.001)   # 1ms poll — tight enough to catch tap release

                if lmb_released_during_delay:
                    # LMB released mid-delay — end of burst, return crosshair if needed
                    if total_y_movement != 0 and state.get_return_crosshair_enabled():
                        makcu_controller.move_mouse_smoothly(
                            0, -total_y_movement, 20, state.get_return_speed()
                        )
                    shot_count       = 0
                    total_y_movement = 0
                    lmb_was_pressed  = False
                    continue   # back to top — do NOT increment shot_count

                shot_count += 1
            else:
                time.sleep(0.02)
