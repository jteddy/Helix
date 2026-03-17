"""
Recoil recorder — captures raw mouse movement via MAKCU mouse streaming.

Uses km.mouse(1,1) (raw physical input mode) — no OS hooks, anti-cheat safe.

Workflow:
  1. arm(result_callback, bucket_ms)
  2. User fires in-game (hold LMB → release LMB)
  3. result_callback(vectors) fires with [(x, y, delay_ms), ...]
  4. Recorder auto-disarms after one successful capture
"""

import time
import threading
from typing import Callable, List, Optional, Tuple


MIN_HOLD_MS = 200  # Ignore clicks shorter than this (UI clicks, menus, etc.)


class recorder:
    _armed: bool = False
    _recording: bool = False
    _events: List[Tuple[float, int, int]] = []  # (perf_counter, dx, dy)
    _lmb_down_at: float = 0.0
    _lock = threading.Lock()
    _result_callback: Optional[Callable] = None
    _bucket_ms: int = 85

    @staticmethod
    def _bucket(events: List[Tuple], bucket_ms: int) -> List[Tuple]:
        """Group raw delta events into fixed-width time buckets (one per shot)."""
        if not events:
            return []
        bucket_sec = bucket_ms / 1000.0
        t0 = events[0][0]
        bucket_end = t0 + bucket_sec
        buckets = []
        cx = cy = 0
        for ts, dx, dy in events:
            if ts <= bucket_end:
                cx += dx
                cy += dy
            else:
                buckets.append((round(cx), round(cy), bucket_ms))
                cx, cy = dx, dy
                while bucket_end < ts:
                    bucket_end += bucket_sec
        if cx or cy:
            buckets.append((round(cx), round(cy), bucket_ms))
        return buckets

    @staticmethod
    def _on_mouse_frame(buttons: int, dx: int, dy: int) -> None:
        """Called by the makcu listener thread for every mouse streaming frame."""
        lmb = bool(buttons & 0x01)
        pending_callback = None
        pending_buckets = None

        with recorder._lock:
            if not recorder._armed:
                return

            if lmb and not recorder._recording:
                recorder._recording = True
                recorder._events = []
                recorder._lmb_down_at = time.perf_counter()
                print("[Recorder] ● Recording…")
                return

            if lmb and recorder._recording:
                if dx != 0 or dy != 0:
                    recorder._events.append((time.perf_counter(), dx, dy))
                return

            if not lmb and recorder._recording:
                recorder._recording = False
                held_ms = (time.perf_counter() - recorder._lmb_down_at) * 1000
                events = list(recorder._events)

                if held_ms < MIN_HOLD_MS:
                    print(f"[Recorder] Click ignored ({held_ms:.0f} ms — too short)")
                    return

                print(f"[Recorder] ■ Stopped ({held_ms:.0f} ms, {len(events)} delta events)")
                buckets = recorder._bucket(events, recorder._bucket_ms)
                if buckets and recorder._result_callback:
                    pending_callback = recorder._result_callback
                    pending_buckets = buckets

        # Fire callback outside the lock to prevent deadlock
        if pending_callback and pending_buckets:
            pending_callback(pending_buckets)

    @staticmethod
    def arm(result_callback: Callable, bucket_ms: int = 85) -> bool:
        from mouse.makcu import makcu_controller
        with recorder._lock:
            if recorder._armed:
                return False
            if not makcu_controller.is_connected():
                return False
            recorder._armed = True
            recorder._recording = False
            recorder._events = []
            recorder._bucket_ms = bucket_ms
            recorder._result_callback = result_callback

        ok = makcu_controller.start_recording(recorder._on_mouse_frame)
        if not ok:
            with recorder._lock:
                recorder._armed = False
            return False
        print("[Recorder] Armed")
        return True

    @staticmethod
    def disarm() -> None:
        from mouse.makcu import makcu_controller
        with recorder._lock:
            if not recorder._armed:
                return
            recorder._armed = False
            recorder._recording = False

        makcu_controller.stop_recording()
        print("[Recorder] Disarmed")

    @staticmethod
    def is_armed() -> bool:
        return recorder._armed

    @staticmethod
    def is_recording() -> bool:
        return recorder._recording
