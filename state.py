"""
AppState — single source of truth for all runtime settings.
Replaces the tkinter RecoilMenu / FlashlightMenu / SettingsMenu classes.
Thread-safe: all loops and the HTTP layer share this one object.
"""
import os
import random
import threading
from typing import List, Tuple


class AppState:
    def __init__(self):
        self._lock = threading.RLock()

        # ── Recoil ────────────────────────────────────────────────────────────
        self.recoil_enabled = False
        self.toggle_keybind = "NONE"
        self.cycle_keybind = "NONE"
        self.require_aim = False
        self.loop_recoil = False
        self.randomisation = False
        self.return_crosshair = False
        self.randomisation_strength: float = 0.5
        self.recoil_scalar: float = 1.0
        self.x_control: float = 1.0
        self.y_control: float = 1.0
        self.return_speed: float = 0.5
        self.scripts_dir: str = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "saved_scripts"
        )
        self.loaded_script: str = "NONE"
        self.vectors: List[Tuple[float, float, float]] = []

        # ── Flashlight ────────────────────────────────────────────────────────
        self.flashlight_enabled = False
        self.flashlight_keybind = "NONE"
        self.hold_threshold_ms: float = 50.0
        self.cooldown_ms: float = 500.0
        self.pre_fire_min_ms: float = 15.0
        self.pre_fire_max_ms: float = 15.0

        # ── Settings ──────────────────────────────────────────────────────────
        self.game_scalar: str = "Manual"
        self.game_sensitivity: float = 1.0

    # ── Recoil interface (matches original RecoilMenu method names) ───────────

    def get_is_enabled(self) -> bool:
        return self.recoil_enabled

    def toggle_recoil(self):
        self.recoil_enabled = not self.recoil_enabled

    def get_toggle_keybind(self) -> str:
        return self.toggle_keybind

    def get_cycle_bind(self) -> str:
        return self.cycle_keybind

    def requires_right_button(self) -> bool:
        return self.require_aim

    def get_is_recoil_looped(self) -> bool:
        return self.loop_recoil

    def get_is_randomisation_enabled(self) -> bool:
        return self.randomisation

    def get_randomisation_strength(self) -> float:
        return self.randomisation_strength

    def get_recoil_scalar(self) -> float:
        return self.recoil_scalar

    def get_x_control(self) -> float:
        return self.x_control

    def get_y_control(self) -> float:
        return self.y_control

    def get_return_crosshair_enabled(self) -> bool:
        return self.return_crosshair

    def get_return_speed(self) -> float:
        return self.return_speed

    # ── Settings interface ────────────────────────────────────────────────────

    def get_game_scalar(self) -> str:
        return self.game_scalar

    def get_game_sensitivity(self) -> float:
        return self.game_sensitivity

    # ── Flashlight interface ──────────────────────────────────────────────────

    def get_is_flashlight_enabled(self) -> bool:
        return self.flashlight_enabled

    def get_flashlight_keybind(self) -> str:
        return self.flashlight_keybind

    def get_hold_threshold(self) -> float:
        return max(0.0, self.hold_threshold_ms) / 1000.0

    def get_cooldown_seconds(self) -> float:
        return max(0.0, self.cooldown_ms) / 1000.0

    def get_pre_fire_delay(self) -> float:
        lo = max(0.0, self.pre_fire_min_ms)
        hi = max(0.0, self.pre_fire_max_ms)
        if lo > hi:
            lo, hi = hi, lo
        return random.uniform(lo, hi) / 1000.0

    # ── Script management ─────────────────────────────────────────────────────

    def list_scripts(self) -> List[str]:
        if not os.path.isdir(self.scripts_dir):
            return []
        return sorted(f[:-4] for f in os.listdir(self.scripts_dir) if f.endswith(".txt"))

    def load_script(self, name: str) -> bool:
        path = os.path.join(self.scripts_dir, f"{name}.txt")
        if not os.path.exists(path):
            return False
        with open(path, "r") as f:
            content = f.read()
        self.loaded_script = name
        self.vectors = self._parse_vectors(content)
        return True

    def save_script(self, name: str, content: str) -> bool:
        os.makedirs(self.scripts_dir, exist_ok=True)
        with open(os.path.join(self.scripts_dir, f"{name}.txt"), "w") as f:
            f.write(content)
        return True

    def delete_script(self, name: str) -> bool:
        path = os.path.join(self.scripts_dir, f"{name}.txt")
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def cycle_script(self):
        scripts = self.list_scripts()
        if not scripts:
            return
        if self.loaded_script in scripts:
            idx = (scripts.index(self.loaded_script) + 1) % len(scripts)
        else:
            idx = 0
        self.load_script(scripts[idx])

    @staticmethod
    def _parse_vectors(text: str) -> List[Tuple[float, float, float]]:
        out = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                x, y, d = map(str.strip, line.split(","))
                out.append((float(x), float(y), float(d) / 1000))
            except Exception:
                pass
        return out

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "recoil": {
                "enabled": self.recoil_enabled,
                "toggle_keybind": self.toggle_keybind,
                "cycle_keybind": self.cycle_keybind,
                "require_aim": self.require_aim,
                "loop_recoil": self.loop_recoil,
                "randomisation": self.randomisation,
                "return_crosshair": self.return_crosshair,
                "randomisation_strength": self.randomisation_strength,
                "recoil_scalar": self.recoil_scalar,
                "x_control": self.x_control,
                "y_control": self.y_control,
                "return_speed": self.return_speed,
                "scripts_dir": self.scripts_dir,
                "loaded_script": self.loaded_script,
            },
            "flashlight": {
                "enabled": self.flashlight_enabled,
                "keybind": self.flashlight_keybind,
                "hold_threshold_ms": self.hold_threshold_ms,
                "cooldown_ms": self.cooldown_ms,
                "pre_fire_min_ms": self.pre_fire_min_ms,
                "pre_fire_max_ms": self.pre_fire_max_ms,
            },
            "settings": {
                "game_scalar": self.game_scalar,
                "game_sensitivity": self.game_sensitivity,
            },
        }

    def from_dict(self, data: dict):
        r = data.get("recoil", {})
        self.recoil_enabled        = r.get("enabled", False)
        self.toggle_keybind        = r.get("toggle_keybind", "NONE")
        self.cycle_keybind         = r.get("cycle_keybind", "NONE")
        self.require_aim           = r.get("require_aim", False)
        self.loop_recoil           = r.get("loop_recoil", False)
        self.randomisation         = r.get("randomisation", False)
        self.return_crosshair      = r.get("return_crosshair", False)
        self.randomisation_strength= float(r.get("randomisation_strength", 0.5))
        self.recoil_scalar         = float(r.get("recoil_scalar", 1.0))
        self.x_control             = float(r.get("x_control", 1.0))
        self.y_control             = float(r.get("y_control", 1.0))
        self.return_speed          = float(r.get("return_speed", 0.5))
        if "scripts_dir" in r and os.path.isdir(r["scripts_dir"]):
            self.scripts_dir = r["scripts_dir"]
        if r.get("loaded_script", "NONE") != "NONE":
            self.load_script(r["loaded_script"])

        fl = data.get("flashlight", {})
        self.flashlight_enabled  = fl.get("enabled", False)
        self.flashlight_keybind  = fl.get("keybind", "NONE")
        self.hold_threshold_ms   = float(fl.get("hold_threshold_ms", 50.0))
        self.cooldown_ms         = float(fl.get("cooldown_ms", 500.0))
        self.pre_fire_min_ms     = float(fl.get("pre_fire_min_ms", 15.0))
        self.pre_fire_max_ms     = float(fl.get("pre_fire_max_ms", 15.0))

        s = data.get("settings", {})
        self.game_scalar      = s.get("game_scalar", "Manual")
        self.game_sensitivity = float(s.get("game_sensitivity", 1.0))
