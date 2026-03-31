"""
AppState — single source of truth for all runtime settings.
Replaces the tkinter RecoilMenu / FlashlightMenu / SettingsMenu classes.
Thread-safe: all loops and the HTTP layer share this one object.
"""
import json
import os
import pathlib
import random
import threading
from typing import List, Optional, Tuple


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
        self.script_sensitivity: float = 1.0
        self.vectors: List[Tuple[float, float, float]] = []
        self.burst_history: List[float] = []

        # ── Flashlight ────────────────────────────────────────────────────────
        self.flashlight_enabled = False
        self.flashlight_keybind = "NONE"
        self.hold_threshold_ms: float = 50.0
        self.cooldown_ms: float = 800.0
        self.pre_fire_min_ms: float = 50.0
        self.pre_fire_max_ms: float = 180.0

        # ── Settings ──────────────────────────────────────────────────────────
        self.game_scalar: str = "Manual"
        self.game_sensitivity: float = 1.0
        self.theme: str = "Default"

        # ── CS2 built-in weapon override ──────────────────────────────────────
        # "none" means use the loaded script; any other value is a key from
        # features.cs2.weapon_data.CS2_WEAPONS (e.g. "ak47", "m4a1s").
        self.cs2_weapon: str = "none"

    # ── Recoil interface (matches original RecoilMenu method names) ───────────

    def get_is_enabled(self) -> bool:
        with self._lock:
            return self.recoil_enabled

    def toggle_recoil(self):
        with self._lock:
            self.recoil_enabled = not self.recoil_enabled

    def toggle_flashlight(self):
        with self._lock:
            self.flashlight_enabled = not self.flashlight_enabled

    def get_toggle_keybind(self) -> str:
        with self._lock:
            return self.toggle_keybind

    def get_cycle_bind(self) -> str:
        with self._lock:
            return self.cycle_keybind

    def requires_right_button(self) -> bool:
        with self._lock:
            return self.require_aim

    def get_is_recoil_looped(self) -> bool:
        with self._lock:
            return self.loop_recoil

    def get_is_randomisation_enabled(self) -> bool:
        with self._lock:
            return self.randomisation

    def get_randomisation_strength(self) -> float:
        with self._lock:
            return self.randomisation_strength

    def get_recoil_scalar(self) -> float:
        with self._lock:
            return self.recoil_scalar

    def get_x_control(self) -> float:
        with self._lock:
            return self.x_control

    def get_y_control(self) -> float:
        with self._lock:
            return self.y_control

    def get_return_crosshair_enabled(self) -> bool:
        with self._lock:
            return self.return_crosshair

    def get_return_speed(self) -> float:
        with self._lock:
            return self.return_speed

    def get_vectors(self) -> List[Tuple[float, float, float]]:
        """Return a thread-safe snapshot of the current recoil vector list.
        The recoil loop should call this instead of reading self.vectors directly,
        so a concurrent script load can never mutate the list mid-spray."""
        with self._lock:
            return list(self.vectors)

    def get_active_vectors(self) -> List[Tuple[float, float, float]]:
        """Return the active recoil pattern.
        If a CS2 built-in weapon is selected it takes priority over the loaded
        script; otherwise falls back to the parsed script vectors."""
        with self._lock:
            weapon = self.cs2_weapon
        if weapon and weapon != "none":
            from features.cs2.weapon_data import CS2_WEAPONS
            pattern = CS2_WEAPONS.get(weapon)
            if pattern:
                return list(pattern)
        with self._lock:
            return list(self.vectors)

    # ── CS2 weapon ────────────────────────────────────────────────────────────

    def get_cs2_weapon(self) -> str:
        with self._lock:
            return self.cs2_weapon

    def set_cs2_weapon(self, weapon: str):
        from features.cs2.weapon_data import CS2_WEAPONS
        if weapon != "none" and weapon not in CS2_WEAPONS:
            raise ValueError(f"Unknown CS2 weapon: {weapon!r}")
        with self._lock:
            self.cs2_weapon = weapon

    # ── Burst history (runtime-only, not persisted) ─────────────────────────

    def add_burst(self, duration_ms: float):
        with self._lock:
            self.burst_history.append(round(duration_ms))
            if len(self.burst_history) > 5:
                self.burst_history = self.burst_history[-5:]

    def get_burst_history(self) -> List[float]:
        with self._lock:
            return list(self.burst_history)

    # ── Settings interface ────────────────────────────────────────────────────

    def get_game_scalar(self) -> str:
        with self._lock:
            return self.game_scalar

    def get_game_sensitivity(self) -> float:
        with self._lock:
            return self.game_sensitivity

    # ── Flashlight interface ──────────────────────────────────────────────────

    def get_is_flashlight_enabled(self) -> bool:
        with self._lock:
            return self.flashlight_enabled

    def get_flashlight_keybind(self) -> str:
        with self._lock:
            return self.flashlight_keybind

    def get_hold_threshold(self) -> float:
        with self._lock:
            return max(0.0, self.hold_threshold_ms) / 1000.0

    def get_cooldown_seconds(self) -> float:
        with self._lock:
            return max(0.0, self.cooldown_ms) / 1000.0

    def get_pre_fire_delay(self) -> float:
        with self._lock:
            lo = max(0.0, self.pre_fire_min_ms)
            hi = max(0.0, self.pre_fire_max_ms)
            if lo > hi:
                lo, hi = hi, lo
            return random.uniform(lo, hi) / 1000.0

    # ── Script management ─────────────────────────────────────────────────────

    def list_games(self) -> List[str]:
        with self._lock:
            if not os.path.isdir(self.scripts_dir):
                return []
            return sorted(d for d in os.listdir(self.scripts_dir)
                          if os.path.isdir(os.path.join(self.scripts_dir, d)))

    def list_scripts(self, game: Optional[str] = None) -> List[str]:
        with self._lock:
            base = pathlib.Path(self.scripts_dir).resolve()
            if game:
                folder = (base / game).resolve()
                if not str(folder).startswith(str(base) + os.sep):
                    return []
            else:
                folder = base
            if not folder.is_dir():
                return []
            json_names = {f[:-5] for f in os.listdir(str(folder)) if f.endswith(".json")}
            txt_names = {f[:-4] for f in os.listdir(str(folder)) if f.endswith(".txt")}
            return sorted(json_names | txt_names)

    def _resolve_path(self, name: str, game: Optional[str] = None, ext: str = ".json") -> str:
        """Return the absolute path for a script file.

        Validates that the resolved path stays within scripts_dir to
        prevent path traversal attacks via crafted game/name URL parameters.
        """
        base = pathlib.Path(self.scripts_dir).resolve()
        if game:
            target = (base / game / f"{name}{ext}").resolve()
        else:
            target = (base / f"{name}{ext}").resolve()

        if not str(target).startswith(str(base) + os.sep) and str(target) != str(base):
            raise ValueError(f"Path traversal attempt blocked: {target}")

        return str(target)

    def load_script(self, name: str, game: Optional[str] = None) -> bool:
        try:
            json_path = self._resolve_path(name, game, ext=".json")
            txt_path = self._resolve_path(name, game, ext=".txt")
        except ValueError:
            return False

        if os.path.exists(json_path):
            with open(json_path, "r") as f:
                data = json.load(f)
            sensitivity = float(data.get("sensitivity", 1.0))
            vectors = self._parse_vectors_json(data.get("steps", []))
        elif os.path.exists(txt_path):
            with open(txt_path, "r") as f:
                text = f.read()
            sensitivity = 1.0
            vectors = self._parse_vectors(text)
        else:
            return False

        with self._lock:
            self.loaded_script = f"{game}/{name}" if game else name
            self.script_sensitivity = sensitivity
            self.vectors = vectors
        return True

    def save_script(self, name: str, content: str, game: Optional[str] = None,
                    sensitivity: float = 1.0) -> bool:
        try:
            path = self._resolve_path(name, game, ext=".json")
        except ValueError:
            return False
        steps = []
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                x, y, d = map(str.strip, line.split(","))
                steps.append([float(x), float(y), float(d)])
            except Exception:
                pass
        payload = {
            "version": 1,
            "game": game or "",
            "author": "",
            "sensitivity": float(sensitivity),
            "steps": steps,
        }
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(payload, f, indent=2)
        return True

    def delete_script(self, name: str, game: Optional[str] = None) -> bool:
        try:
            json_path = self._resolve_path(name, game, ext=".json")
            txt_path = self._resolve_path(name, game, ext=".txt")
        except ValueError:
            return False
        deleted = False
        for path in (json_path, txt_path):
            if os.path.exists(path):
                os.remove(path)
                deleted = True
        if deleted and game:
            folder = os.path.join(self.scripts_dir, game)
            try:
                if not os.listdir(folder):
                    os.rmdir(folder)
            except Exception:
                pass
        return deleted

    def cycle_script(self):
        with self._lock:
            # Determine which game folder the current script belongs to
            current_game = None
            if self.loaded_script and "/" in self.loaded_script:
                current_game = self.loaded_script.rsplit("/", 1)[0]

            # Only cycle within that game's scripts (or root if no game)
            scripts = self.list_scripts(current_game)
            if not scripts:
                return

            # Strip game prefix to get just the script name for comparison
            current_name = self.loaded_script
            if current_game and current_name.startswith(current_game + "/"):
                current_name = current_name[len(current_game) + 1:]

            # Find current script and advance to next
            try:
                current_idx = scripts.index(current_name)
                idx = (current_idx + 1) % len(scripts)
            except ValueError:
                idx = 0
            name = scripts[idx]
        self.load_script(name, current_game)

    @staticmethod
    def _parse_vectors_json(steps: list) -> List[Tuple[float, float, float]]:
        out = []
        for item in steps:
            try:
                x, y, d = float(item[0]), float(item[1]), float(item[2])
                out.append((x, y, d / 1000))
            except Exception:
                pass
        return out

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
        with self._lock:
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
                    "script_sensitivity": self.script_sensitivity,
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
                    "theme": self.theme,
                    "cs2_weapon": self.cs2_weapon,
                },
            }

    def from_dict(self, data: dict):
        r = data.get("recoil", {})
        with self._lock:
            self.recoil_enabled         = r.get("enabled", False)
            self.toggle_keybind         = r.get("toggle_keybind", "NONE")
            self.cycle_keybind          = r.get("cycle_keybind", "NONE")
            self.require_aim            = r.get("require_aim", False)
            self.loop_recoil            = r.get("loop_recoil", False)
            self.randomisation          = r.get("randomisation", False)
            self.return_crosshair       = r.get("return_crosshair", False)
            self.randomisation_strength = float(r.get("randomisation_strength", 0.5))
            self.recoil_scalar          = float(r.get("recoil_scalar", 1.0))
            self.x_control              = float(r.get("x_control", 1.0))
            self.y_control              = float(r.get("y_control", 1.0))
            self.return_speed           = float(r.get("return_speed", 0.5))
            if "scripts_dir" in r and os.path.isdir(r["scripts_dir"]):
                self.scripts_dir = r["scripts_dir"]

        # Correctly split "game/name" before calling load_script
        loaded = r.get("loaded_script", "NONE")
        # Never auto-reload the workshop spread script on startup —
        # it is a temporary tool script and should not run as recoil compensation
        if loaded != "NONE" and loaded != "workshop_spread" and not loaded.endswith("/workshop_spread"):
            if "/" in loaded:
                game, name = loaded.split("/", 1)
                self.load_script(name, game)
            else:
                self.load_script(loaded)

        with self._lock:
            fl = data.get("flashlight", {})
            self.flashlight_enabled = fl.get("enabled", False)
            self.flashlight_keybind = fl.get("keybind", "NONE")
            self.hold_threshold_ms  = float(fl.get("hold_threshold_ms", 50.0))
            self.cooldown_ms        = float(fl.get("cooldown_ms", 500.0))
            self.pre_fire_min_ms    = float(fl.get("pre_fire_min_ms", 15.0))
            self.pre_fire_max_ms    = float(fl.get("pre_fire_max_ms", 15.0))

            s = data.get("settings", {})
            self.game_scalar      = s.get("game_scalar", "Manual")
            self.game_sensitivity = float(s.get("game_sensitivity", 1.0))
            self.theme            = s.get("theme", "Default")
            self.cs2_weapon       = s.get("cs2_weapon", "none")
