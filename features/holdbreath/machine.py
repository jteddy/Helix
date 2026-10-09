"""Hold Breath state machine: pure logic, no I/O, no threads.

The loop (holdbreath.py) calls step() every few ms with the aim button state, whether
Hold Breath is active, and a settings snapshot; step() returns the key actions to send.
See docs/superpowers/specs/2026-10-09-hold-breath-design.md for the state table."""
from dataclasses import dataclass

IDLE, WAITING, BREATHING, SPENT = "idle", "waiting", "breathing", "spent"


@dataclass(frozen=True)
class HoldBreathConfig:
    trigger: str = "RMB"
    ads_mode: str = "hold"         # hold | toggle
    breath_mode: str = "hold"      # hold | toggle
    key: str = "NONE"
    tap_on_release: bool = False
    delay_ms: float = 0.0
    max_hold_ms: float = 0.0       # 0 = no limit

    @classmethod
    def from_settings(cls, d):
        return cls(
            trigger=d["trigger"], ads_mode=d["ads_mode"], breath_mode=d["breath_mode"],
            key=d["key"], tap_on_release=bool(d["tap_on_release"]),
            delay_ms=float(d["delay_ms"]), max_hold_ms=float(d["max_hold_ms"]),
        )

    def identity(self):
        """Settings whose change ends a breath in progress and resets aiming."""
        return (self.key, self.breath_mode, self.trigger, self.ads_mode)


class HoldBreathMachine:
    def __init__(self):
        self.reset()

    def reset(self):
        self.phase = IDLE
        self.aiming = False
        self._prev_trigger = False
        self._t_aim = 0.0
        self._t_breath = 0.0
        self._cfg = None

    def step(self, now, trigger_down, active, cfg):
        actions = []
        prev = self._cfg
        if prev is not None and prev.identity() != cfg.identity():
            actions += self._stop(prev)          # release with the settings it started with
            self._idle(trigger_down)
        self._cfg = cfg

        if not active:
            actions += self._stop(cfg)
            self._idle(trigger_down)
            return actions

        pressed = trigger_down and not self._prev_trigger
        self._prev_trigger = trigger_down
        if cfg.ads_mode == "toggle":
            if pressed:
                self.aiming = not self.aiming
        else:
            self.aiming = trigger_down

        if self.phase == IDLE and self.aiming:
            self.phase, self._t_aim = WAITING, now

        if self.phase == WAITING:
            if not self.aiming:
                self.phase = IDLE
            elif (now - self._t_aim) * 1000.0 >= cfg.delay_ms:
                actions.append(("down" if cfg.breath_mode == "hold" else "tap", cfg.key))
                self.phase, self._t_breath = BREATHING, now
        elif self.phase == BREATHING:
            if not self.aiming:
                actions += self._stop(cfg)
                self.phase = IDLE
            elif cfg.max_hold_ms > 0 and (now - self._t_breath) * 1000.0 >= cfg.max_hold_ms:
                actions.append(("up" if cfg.breath_mode == "hold" else "tap", cfg.key))
                self.phase = SPENT
        elif self.phase == SPENT and not self.aiming:
            self.phase = IDLE
        return actions

    def _stop(self, cfg):
        """Actions that end a breath in progress (none unless BREATHING)."""
        if self.phase != BREATHING:
            return []
        if cfg.breath_mode == "hold":
            return [("up", cfg.key)]
        return [("tap", cfg.key)] if cfg.tap_on_release else []

    def _idle(self, trigger_down):
        self.phase = IDLE
        self.aiming = False
        self._prev_trigger = trigger_down     # a button already held is not a new press
