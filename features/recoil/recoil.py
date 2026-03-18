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
        shot_count        = 0
        total_y_movement  = 0
        lmb_was_pressed   = False
        last_toggle_state = False
        last_cycle_state  = False
        last_toggle_time  = 0.0
        last_cycle_time   = 0.0
        rand_drift_x      = 0.0
        rand_drift_y      = 0.0
        DEBOUNCE = 0.3

        # FIX: _reset_burst was previously redefined inside the while loop on
        # every iteration (~every 5 ms in the hot path). Defining it once here
        # as a plain function that accepts its inputs avoids the repeated closure
        # allocation and makes the data flow explicit.
        def _reset_burst(y_movement: float) -> None:
            if y_movement != 0 and state.get_return_crosshair_enabled():
                makcu_controller.move_mouse_smoothly(
                    0, -y_movement, 20, state.get_return_speed()
                )

        while True:
            try:
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

                recoil_pattern = state.get_vectors()
                lmb_pressed    = makcu_controller.get_button_state("LMB")

                # ── LMB released — optionally return crosshair ────────────────────
                if not lmb_pressed and lmb_was_pressed and total_y_movement != 0:
                    if state.get_return_crosshair_enabled():
                        makcu_controller.move_mouse_smoothly(0, -total_y_movement, 20, state.get_return_speed())
                    total_y_movement = 0
                    shot_count       = 0
                    lmb_was_pressed  = False
                    time.sleep(0.005)
                    continue

                if not lmb_pressed:
                    shot_count       = 0
                    total_y_movement = 0
                    lmb_was_pressed  = False
                    time.sleep(0.005)
                    continue

                # ── LMB just pressed ──────────────────────────────────────────────
                if not lmb_was_pressed:
                    shot_count       = 0
                    total_y_movement = 0
                    rand_drift_x     = 0.0
                    rand_drift_y     = 0.0
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

                    scalar   = recoil.sens_scalar(state)
                    actual_x = x * state.get_x_control() * scalar
                    actual_y = y * state.get_y_control() * scalar

                    if state.get_is_randomisation_enabled():
                        strength = state.get_randomisation_strength()
                        # Drift random-walks each burst with decay to keep it bounded.
                        # Hard-clamp to ±strength so very long sprays can't drift
                        # excessively (without the clamp, max drift = strength/(1-0.85)
                        # = 6.7× strength, which is visually too large at high settings).
                        rand_drift_x = rand_drift_x * 0.85 + random.uniform(-strength, strength)
                        rand_drift_y = rand_drift_y * 0.85 + random.uniform(-strength, strength)
                        rand_drift_x = max(-strength, min(strength, rand_drift_x))
                        rand_drift_y = max(-strength, min(strength, rand_drift_y))
                        actual_x = recoil.jitter(actual_x, strength) + rand_drift_x
                        actual_y = recoil.jitter(actual_y, strength) + rand_drift_y

                    start_time     = time.perf_counter()
                    move_completed = makcu_controller.move_mouse_smoothly(
                        actual_x, actual_y, interrupt_on_lmb_release=True
                    )

                    if move_completed:
                        total_y_movement += actual_y

                    # ── Case 1: move was interrupted — LMB released during move ───
                    # Reset immediately, skip the inter-shot delay entirely.
                    # Do NOT re-check LMB here — if it bounced back to True already
                    # that will be handled cleanly at the top of the next iteration.
                    if not move_completed:
                        _reset_burst(total_y_movement)
                        shot_count       = 0
                        total_y_movement = 0
                        lmb_was_pressed  = False
                        continue

                    # ── Case 2: move completed — poll LMB during inter-shot delay ─
                    # Check LMB immediately (catches release in the tiny gap between
                    # move completing and the poll starting), then keep polling every
                    # 1 ms for the remainder of the inter-shot delay.
                    elapsed   = time.perf_counter() - start_time
                    remaining = delay - elapsed

                    lmb_released = not makcu_controller.get_button_state("LMB")

                    if not lmb_released and remaining > 0:
                        deadline = time.perf_counter() + remaining
                        while time.perf_counter() < deadline:
                            if not makcu_controller.get_button_state("LMB"):
                                lmb_released = True
                                break
                            time.sleep(0.001)

                    if lmb_released:
                        _reset_burst(total_y_movement)
                        shot_count       = 0
                        total_y_movement = 0
                        lmb_was_pressed  = False
                        continue

                    shot_count += 1
                else:
                    time.sleep(0.02)

            except Exception as e:
                print(f"[Recoil] Unexpected error — thread continues: {e}")
                shot_count       = 0
                total_y_movement = 0
                lmb_was_pressed  = False
                time.sleep(0.1)
