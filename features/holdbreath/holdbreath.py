"""Hold Breath loop: watches the aim button and drives HoldBreathMachine.

Started by main.py's lifespan next to the Recoil and Flashlight loops. Every key action
goes through the shared keyboard queue (mouse/keyboard.py), so it never overlaps a
Flashlight Key tap."""
import time

from features.holdbreath.machine import HoldBreathConfig, HoldBreathMachine
from mouse.makcu import makcu_controller, keyboard as default_keyboard

POLL_S = 0.005


def _controller():
    """The live controller object, or None while disconnected."""
    with makcu_controller.connection_lock:
        return makcu_controller.controller if makcu_controller.is_connected_flag else None


def run_hold_breath(state, kb=None, stop=None, clock=time.monotonic, sleep=time.sleep):
    kb = kb or default_keyboard
    machine = HoldBreathMachine()
    last_ctrl = None
    while stop is None or not stop.is_set():
        try:
            settings = state.get_hold_breath()
            cfg = HoldBreathConfig.from_settings(settings)
            ctrl = _controller()
            if ctrl is not None and ctrl is not last_ctrl:
                # First connect or a reconnect: a key may still be down on the gaming PC
                # from before (crash, kill, dropped link). Release it and start clean;
                # release_all() also covers a key-up lost while the MAKCU was gone, even
                # if the key setting has changed since.
                if cfg.key != "NONE":
                    kb.up(cfg.key)
                kb.release_all()
                machine.reset()
            last_ctrl = ctrl
            active = (settings["enabled"] and state.get_is_enabled()
                      and cfg.key != "NONE" and ctrl is not None)
            trigger_down = makcu_controller.get_button_state(cfg.trigger)
            for op, key in machine.step(clock(), trigger_down, active, cfg):
                getattr(kb, op)(key)              # "down" | "up" | "tap"
                print(f"[HoldBreath] {op} {key}")
        except Exception as e:
            print(f"[HoldBreath] Unexpected error — releasing keys, thread continues: {e}")
            kb.release_all()
            machine.reset()
        sleep(POLL_S)
