"""
Pattern recorder — records the user's own physical mouse compensation while
they spray, by polling the firmware's tracked pointer (km.getpos), then turns
the path into recoil steps (x, y, delay_ms).

V4 firmware has no mouse-motion stream, so getpos polling is the only way to
read movement. The position is the sum of every mouse report sent to the PC
(physical + injected) clamped to the km.screen virtual screen, so recording
needs Recoil OFF (and optionally a wide virtual screen for very long pulls).
"""
import bisect
import threading
import time
from collections import deque

from mouse.makcu import makcu_controller

# Polling flat out (hundreds of queries/s) starves the firmware's button-event stream:
# on overflow it disables the stream, so left-click is never seen. 100 Hz is plenty for
# patterns whose steps are tens of ms long.
POLL_INTERVAL = 0.01
STREAM_REASSERT_S = 3.0
ARM_TIMEOUT_S = 120
MAX_SAMPLES = 20000
MAX_QUERY_FAILS = 25
VIRTUAL_SCREEN = 30000
PATH_POINTS = 400


class RecorderError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _pos_at(ts, xs, ys, t):
    if t <= ts[0]:
        return xs[0], ys[0]
    if t >= ts[-1]:
        return xs[-1], ys[-1]
    i = bisect.bisect_right(ts, t)
    span = ts[i] - ts[i - 1]
    f = (t - ts[i - 1]) / span if span > 0 else 0.0
    return xs[i - 1] + (xs[i] - xs[i - 1]) * f, ys[i - 1] + (ys[i] - ys[i - 1]) * f


def build_pattern(samples, interval_ms, shots=None, lead_ms=0.0):
    """samples: [(t_ms, x, y)] relative to the first sample, t increasing.
    Step k is the movement made in the window [k*I + lead, (k+1)*I + lead], so
    a positive lead moves compensation earlier to offset human reaction delay.
    Returns [[dx, dy, interval_ms], ...]."""
    if len(samples) < 2:
        raise ValueError("Not enough samples")
    if interval_ms <= 0:
        raise ValueError("interval_ms must be > 0")
    ts = [s[0] for s in samples]
    xs = [s[1] for s in samples]
    ys = [s[2] for s in samples]
    n = int(shots) if shots else max(1, round(ts[-1] / interval_ms))
    steps = []
    for k in range(n):
        ax, ay = _pos_at(ts, xs, ys, k * interval_ms + lead_ms)
        bx, by = _pos_at(ts, xs, ys, (k + 1) * interval_ms + lead_ms)
        steps.append([round(bx - ax, 1), round(by - ay, 1), round(interval_ms, 1)])
    return steps


def downsample(samples, limit=PATH_POINTS):
    if len(samples) <= limit:
        return [[round(t, 1), x, y] for t, x, y in samples]
    stride = len(samples) / limit
    picked = [samples[int(i * stride)] for i in range(limit)]
    picked[-1] = samples[-1]
    return [[round(t, 1), x, y] for t, x, y in picked]


class Recorder:
    def __init__(self):
        self._lock = threading.Lock()
        self._thread = None
        self._cancel = threading.Event()
        self._finish = threading.Event()
        self._samples = []
        self._pub = self._blank()

    @staticmethod
    def _blank():
        return {
            "state": "idle", "message": "", "samples": 0, "duration_ms": 0.0,
            "pos": None, "rate_hz": None, "clamped": False, "lmb": False,
        }

    def _set(self, **kw):
        with self._lock:
            self._pub.update(kw)

    def status(self):
        with self._lock:
            return dict(self._pub)

    # ── Control ───────────────────────────────────────────────────────────

    def arm(self, state, trigger: str, max_s: float, wide: bool = False):
        if trigger not in ("lmb", "now"):
            raise RecorderError(400, "trigger must be 'lmb' or 'now'")
        if not makcu_controller.is_connected():
            raise RecorderError(503, "MAKCU is not connected")
        if state.get_is_enabled():
            raise RecorderError(
                409, "Turn Recoil OFF first, otherwise Helix's own compensation is recorded"
            )
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise RecorderError(409, "A recording is already in progress")
            self._cancel.clear()
            self._finish.clear()
            self._samples = []
            self._pub = self._blank()
            self._pub["state"] = "armed"
            self._pub["message"] = (
                "Waiting for left-click…" if trigger == "lmb" else "Recording…"
            )
            max_s = max(1.0, min(float(max_s), 60.0))
            makcu_controller._recording.set()
            self._thread = threading.Thread(
                target=self._run, args=(state, trigger, max_s, wide),
                daemon=True, name="pattern-recorder",
            )
            self._thread.start()
        return self.status()

    def stop(self):
        self._finish.set()
        self._join(0.8)
        return self.status()

    def cancel(self):
        self._cancel.set()
        self._join(1.0)
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                self._samples = []
                self._pub = self._blank()
        return self.status()

    def _join(self, timeout):
        t = self._thread
        if t is not None and t.is_alive():
            t.join(timeout)

    def result(self, interval_ms: float, shots, lead_ms: float):
        with self._lock:
            samples = list(self._samples)
            clamped = self._pub["clamped"]
        if len(samples) < 2:
            raise RecorderError(409, "Nothing recorded yet")
        try:
            steps = build_pattern(samples, interval_ms, shots, lead_ms)
        except ValueError as e:
            raise RecorderError(400, str(e))
        return {
            "interval_ms": interval_ms,
            "shots": len(steps),
            "lead_ms": lead_ms,
            "duration_ms": round(samples[-1][0], 1),
            "steps": steps,
            "total": [round(sum(s[0] for s in steps), 1), round(sum(s[1] for s in steps), 1)],
            "path": downsample(samples),
            "clamped": clamped,
        }

    # ── Sampler thread ────────────────────────────────────────────────────

    def _fail(self, message):
        self._set(state="error", message=message, pos=None)

    def _run(self, state, trigger, max_s, wide):
        orig_screen = None
        screen = None
        try:
            # The virtual screen is only resized when asked (wide range): the default
            # 1920x1080, centred, already allows +-540 counts vertically, and resizing is
            # one more device-state change. Its size is still read to detect edge clamping.
            orig_screen = makcu_controller.get_screen()
            screen = orig_screen
            if wide and orig_screen:
                makcu_controller.set_screen(VIRTUAL_SCREEN, VIRTUAL_SCREEN)
                screen = makcu_controller.get_screen() or orig_screen
            makcu_controller.send_text("km.buttons(1)")
            self._sample_loop(state, trigger, max_s, screen)
        except Exception as e:
            print(f"[Recorder] Unexpected error: {e}")
            self._fail(f"Recorder error: {e}")
        finally:
            if wide and orig_screen:
                makcu_controller.set_screen(*orig_screen)
            # The firmware drops the button stream if it overflowed; turn it back on.
            makcu_controller.send_text("km.buttons(1)")
            makcu_controller._recording.clear()

    def _sample_loop(self, state, trigger, max_s, screen):
        pre = deque(maxlen=400)
        samples = []
        phase = "armed"
        base = None
        fails = 0
        polls = 0
        nontext0 = makcu_controller.rx_nontext()[0]
        stream_state = "?"
        last_stream_q = 0.0
        last_phys_q = 0.0
        phys_lmb = False
        phys_raw = "?"
        phys_misses = 0
        lmb_ever = False
        last_pub = 0.0
        clamped = False
        began = time.perf_counter()
        next_poll = began
        last_reassert = began

        def rel(t, x, y):
            return ((t - base[0]) * 1000.0, x - base[1], y - base[2])

        while True:
            if self._cancel.is_set():
                self._set(state="idle", message="Cancelled", pos=None)
                return
            wait = next_poll - time.perf_counter()
            if wait > 0:
                time.sleep(wait)
            now = time.perf_counter()
            next_poll = max(next_poll + POLL_INTERVAL, now)
            if phase == "armed" and not lmb_ever and now - last_reassert >= STREAM_REASSERT_S:
                last_reassert = now
                makcu_controller.send_text("km.buttons(1)")
            if phase == "armed" and now - began > ARM_TIMEOUT_S:
                return self._fail("Timed out waiting for left-click")
            if state.get_is_enabled():
                return self._fail("Recoil was turned on during recording; recording discarded")
            if not makcu_controller.is_connected():
                return self._fail("MAKCU disconnected")

            p = makcu_controller.get_pos()
            t = (now + time.perf_counter()) / 2
            if p is None:
                fails += 1
                if fails >= MAX_QUERY_FAILS:
                    return self._fail(
                        "No reply to km.getpos(); this firmware may not support it"
                    )
                time.sleep(0.01)
                continue
            fails = 0
            stream_lmb = makcu_controller.get_button_state("LMB")
            # Fallback when the button stream is silent: V4 answers km.left() with
            # 0 none / 1 physical / 2 injected / 3 both. Newer firmware may report the
            # injected state only, in which case this simply stays 0.
            # Gives up after 3 unanswered queries: each miss costs a 50 ms timeout.
            if phys_misses < 3 and t - last_phys_q >= 0.05:
                last_phys_q = t
                m = makcu_controller.query(
                    "km.left()", r"^[>\s]*(?:km\.left\()?([0-3])\)?\s*$", timeout=0.05, retries=1
                )
                phys_misses = 0 if m else phys_misses + 1
                phys_raw = m.group(1) if m else "?"
                phys_lmb = bool(m and int(m.group(1)) & 1)
            lmb = stream_lmb or phys_lmb

            if phase == "armed":
                pre.append((t, p[0], p[1]))
                first = pre[0]
                polls += 1
                lmb_ever = lmb_ever or lmb
                if t - last_pub >= 0.2:
                    last_pub = t
                    waited = t - began
                    if t - last_stream_q >= 1.0:
                        last_stream_q = t
                        m = makcu_controller.query(
                            "km.buttons()", r"^[>\s]*(?:km\.buttons\()?([01])\)?\s*$",
                            timeout=0.1, retries=1,
                        )
                        stream_state = ("on" if m.group(1) == "1" else "OFF") if m else "?"
                    nontext, last_frame = makcu_controller.rx_nontext()
                    sent = nontext - nontext0
                    msg = (
                        f"Waiting for left-click… getpos {polls / waited:.0f} Hz · "
                        f"left-click {'HELD' if lmb else 'not seen'} (stream {int(stream_lmb)}, km.left() {phys_raw}) · "
                        f"button stream {stream_state} ({makcu_controller.stream_format()}) · "
                        f"device non-text bytes since arm: {sent}"
                        + (f" (last: {last_frame})" if sent and last_frame else "")
                    )
                    if trigger == "lmb" and waited > 8 and not lmb_ever:
                        msg += " — Helix has not received any left-click from the MAKCU; try 'Start now' then Stop"
                    self._set(
                        pos=[p[0] - first[1], p[1] - first[2]], lmb=lmb,
                        message=msg if trigger == "lmb" else "Recording…",
                    )
                if trigger == "now" or lmb:
                    # Baseline = the sample taken just before the press was seen.
                    base = pre[-2] if len(pre) > 1 else pre[-1]
                    samples = [(0.0, 0, 0)]
                    if base is not pre[-1]:
                        samples.append(rel(*pre[-1]))
                    phase = "recording"
                    self._set(state="recording", message="Recording…")
                continue

            samples.append(rel(t, p[0], p[1]))
            if screen and (
                p[0] <= 0 or p[1] <= 0 or p[0] >= screen[0] - 1 or p[1] >= screen[1] - 1
            ):
                clamped = True
            dur = samples[-1][0]
            self._set(
                samples=len(samples), duration_ms=round(dur, 1),
                pos=[samples[-1][1], samples[-1][2]],
                rate_hz=round(len(samples) / (dur / 1000.0), 1) if dur > 0 else None,
                clamped=clamped, lmb=lmb,
            )
            if (
                self._finish.is_set()
                or (trigger == "lmb" and not lmb)
                or dur >= max_s * 1000.0
                or len(samples) >= MAX_SAMPLES
            ):
                break

        if len(samples) < 3:
            return self._fail("Too few samples recorded")
        moved = any(s[1] or s[2] for s in samples)
        with self._lock:
            self._samples = samples
        self._set(
            state="done",
            message="Done" if moved else "Done, but no mouse movement was detected",
            samples=len(samples), duration_ms=round(samples[-1][0], 1), clamped=clamped,
        )


recorder = Recorder()
