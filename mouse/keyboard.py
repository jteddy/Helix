"""One queue for every keyboard command Helix sends to the MAKCU.

The firmware runs one timed key action (km.press or km.string) at a time and answers
ERR to another key command (press, string, down, up, multidown, multiup) sent while one
is running (mak-suite protocol/KM_API.md, "Timing"). Helix does not read those replies,
so it never overlaps them instead: commands go out in order from one worker thread, and
after a tap the worker waits out the hold before sending the next. The queue also
remembers which keys it holds down, so they can be released on shutdown."""
import queue
import threading
import time

from mouse.keys import key_usage

TAP_MARGIN_MS = 15   # extra wait after a tap's hold before the next key command


class KeyboardQueue:
    def __init__(self, send, sleep=time.sleep):
        """send(cmd) -> bool writes one text command (without CR/LF) to the device."""
        self._send = send
        self._sleep = sleep
        self._q = queue.Queue()
        self._lock = threading.Lock()
        self._held = set()      # HID usages Helix is holding down
        self._pending = 0       # commands queued or being sent
        threading.Thread(target=self._run, daemon=True, name="keyboard").start()

    def tap(self, key, hold_ms=30):
        """Press and release `key` (firmware-timed km.press). False if the name is unknown."""
        usage = key_usage(key)
        if usage is None:
            return False
        hold_ms = int(hold_ms)
        self._put(f"km.press({usage},{hold_ms})", (hold_ms + TAP_MARGIN_MS) / 1000.0)
        return True

    def down(self, key):
        usage = key_usage(key)
        if usage is None:
            return False
        with self._lock:
            self._held.add(usage)
        self._put(f"km.down({usage})", 0.0)
        return True

    def up(self, key):
        usage = key_usage(key)
        if usage is None:
            return False
        with self._lock:
            self._held.discard(usage)
        self._put(f"km.up({usage})", 0.0)
        return True

    def release_all(self):
        """Queue a key up for every key Helix is holding down."""
        with self._lock:
            held, self._held = sorted(self._held), set()
        for usage in held:
            self._put(f"km.up({usage})", 0.0)

    def held(self):
        with self._lock:
            return set(self._held)

    def drain(self, timeout=1.0):
        """Wait until every queued command has been sent. True if that happened in time."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            with self._lock:
                if self._pending == 0:
                    return True
            time.sleep(0.005)
        return False

    def _put(self, cmd, wait_s):
        with self._lock:
            self._pending += 1
        self._q.put((cmd, wait_s))

    def _run(self):
        while True:
            cmd, wait_s = self._q.get()
            try:
                if not self._send(cmd):
                    print(f"[Keyboard] Not sent (MAKCU not connected?): {cmd}")
                if wait_s:
                    self._sleep(wait_s)
            except Exception as e:
                print(f"[Keyboard] {cmd} failed: {e}")
            finally:
                with self._lock:
                    self._pending -= 1
