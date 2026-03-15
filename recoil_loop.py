"""
core/recoil_loop.py
-------------------
The recoil compensation loop. Runs in its own daemon thread.

This is a direct port of Cearum's features/recoil/recoil.py with the
UI menu references replaced by reads from the shared state singleton.

The loop never touches the web layer — it only reads state and writes
to the MAKCU device. Latency is identical to the desktop Cearum app.

Start it once at startup:
    from core.recoil_loop import start_recoil_loop
    start_recoil_loop()
"""

import time
import random
import threading

from core.state       import state
from core.makcu_device import device
from menu.games        import GAME_BASE_SENSITIVITIES


def _jitter(value: float, max_offset: float) -> float:
    return value + random.uniform(-max_offset, max_offset)


def _sens_scalar() -> float:
    """
    Calculate the effective scalar to apply to each vector.
    Mirrors Cearum's sens_scalar logic exactly.
    """
    with state.lock:
        game      = state.game
        sens      = state.sensitivity
        scalar    = state.scalar

    if game in GAME_BASE_SENSITIVITIES:
        base = GAME_BASE_SENSITIVITIES[game]
        return base / max(sens, 0.001)

    # Manual mode — use scalar directly
    return scalar


def _run_loop():
    shot_count      = 0
    total_y_movement = 0.0
    lmb_was_pressed  = False

    print("[Recoil] Loop started.")

    while True:
        # ── Read all settings atomically ──────────────────────────────────────
        with state.lock:
            enabled          = state.enabled
            vectors          = list(state.vectors)
            loop_recoil      = state.loop_recoil
            require_aim      = state.require_aim
            return_crosshair = state.return_crosshair
            return_speed     = state.return_speed
            randomisation    = state.randomisation
            rand_strength    = state.rand_strength
            x_control        = state.x_control
            y_control        = state.y_control

        if not enabled or not vectors:
            shot_count       = 0
            total_y_movement = 0.0
            lmb_was_pressed  = False
            with state.lock:
                state.recoil_active = False
            time.sleep(0.02)
            continue

        lmb_pressed = device.get_button("LMB")

        # ── LMB released — return crosshair if enabled ────────────────────────
        if not lmb_pressed and lmb_was_pressed and total_y_movement != 0:
            if return_crosshair:
                device.move_smooth(0, -total_y_movement, 20, return_speed)
            total_y_movement = 0.0
            shot_count       = 0
            lmb_was_pressed  = False
            with state.lock:
                state.recoil_active = False
            time.sleep(0.02)
            continue

        if not lmb_pressed:
            shot_count       = 0
            total_y_movement = 0.0
            lmb_was_pressed  = False
            with state.lock:
                state.recoil_active = False
            time.sleep(0.02)
            continue

        if not lmb_was_pressed:
            shot_count       = 0
            total_y_movement = 0.0
            lmb_was_pressed  = True

        # ── Require aim (RMB) check ───────────────────────────────────────────
        if require_aim and not device.get_button("RMB"):
            time.sleep(0.02)
            continue

        # ── Shot count bounds ─────────────────────────────────────────────────
        if shot_count >= len(vectors):
            if loop_recoil:
                shot_count = 0
            else:
                time.sleep(0.02)
                continue

        with state.lock:
            state.recoil_active = True

        x, y, delay = vectors[shot_count]

        # Apply randomisation
        if randomisation:
            x = _jitter(x, rand_strength)
            y = _jitter(y, rand_strength)

        scalar   = _sens_scalar()
        actual_x = x * x_control * scalar
        actual_y = y * y_control * scalar

        # ── Fire the movement ─────────────────────────────────────────────────
        start_time     = time.perf_counter()
        move_completed = device.move_smooth(actual_x, actual_y,
                                             interrupt_on_lmb_release=True)

        if move_completed:
            total_y_movement += actual_y

        elapsed   = time.perf_counter() - start_time
        remaining = delay - elapsed
        if remaining > 0:
            time.sleep(remaining)

        shot_count += 1


def start_recoil_loop():
    """Launch the recoil loop as a background daemon thread."""
    t = threading.Thread(target=_run_loop, daemon=True, name="RecoilLoop")
    t.start()
    return t
