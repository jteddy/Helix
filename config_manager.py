"""
Config persistence — saves/loads all settings to config.json on the server.
Uses atomic write (temp file → rename) to prevent corruption on power loss.
"""
import json
import os
import shutil
from state import AppState

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def save(state: AppState) -> None:
    tmp = CONFIG_PATH + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(state.to_dict(), f, indent=2)
        shutil.move(tmp, CONFIG_PATH)
    except Exception as e:
        print(f"[Config] Save error: {e}")
        if os.path.exists(tmp):
            os.remove(tmp)


def load(state: AppState) -> None:
    bak = CONFIG_PATH + ".bak"
    data = _try_load(CONFIG_PATH)

    if data is None and os.path.exists(bak):
        print("[Config] Main config unreadable, trying backup…")
        data = _try_load(bak)

    if data is None:
        print("[Config] No config found — using defaults.")
        return

    try:
        shutil.copy2(CONFIG_PATH, bak)
    except Exception:
        pass

    state.from_dict(data)


def _try_load(path: str) -> dict | None:
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        print(f"[Config] Failed to load {path}: {e}")
        return None
