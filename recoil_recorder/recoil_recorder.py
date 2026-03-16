#!/usr/bin/env python3
"""
recoil_recorder.py — Mouse recoil capture tool for Cearum-Web
=============================================================
Uses the Win32 Raw Input API (RegisterRawInputDevices / WM_INPUT) to read
mouse deltas. No hooks, no external dependencies — just ctypes and the same
Windows API the game itself uses to read your mouse.

Requirements:
  Python 3.7+, Windows only, no pip installs needed.

Workflow:
  1. Turn Cearum recoil OFF in the web UI
  2. Run this script in a terminal (keep it minimised)
  3. Alt-tab into your game and fire a full magazine
  4. Release LMB — the .txt file is saved automatically
  5. Load it in Cearum-Web Scripts panel and tune from there

Usage:
  python recoil_recorder.py
  python recoil_recorder.py --weapon ak47
  python recoil_recorder.py --weapon ak47 --bucket 90
  python recoil_recorder.py --weapon ak47 --out C:/scripts
"""

import argparse
import ctypes
import ctypes.wintypes as wt
import os
import sys
import time
from datetime import datetime

# ── Guard: Windows only ───────────────────────────────────────────────────────
if sys.platform != "win32":
    print("[error] This script requires Windows (Win32 Raw Input API).")
    sys.exit(1)

# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULT_BUCKET_MS  = 85
DEFAULT_OUTPUT_DIR = "."
DEFAULT_WEAPON     = "weapon"
MIN_HOLD_MS        = 150     # ignore clicks shorter than this (menu clicks etc.)

# ── Win32 constants ───────────────────────────────────────────────────────────
WM_INPUT                  = 0x00FF
WM_DESTROY                = 0x0002
WM_CLOSE                  = 0x0010
RID_INPUT                 = 0x10000003
RIDEV_INPUTSINK           = 0x00000100   # receive input even without focus
HID_USAGE_PAGE_GENERIC    = 0x01
HID_USAGE_GENERIC_MOUSE   = 0x02
RI_MOUSE_LEFT_BUTTON_DOWN = 0x0001
RI_MOUSE_LEFT_BUTTON_UP   = 0x0002
CS_VREDRAW                = 0x0001
CS_HREDRAW                = 0x0002
WS_OVERLAPPED             = 0x00000000
HWND_MESSAGE              = wt.HWND(-3)  # message-only window, never visible

user32   = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# ── Win32 structures ──────────────────────────────────────────────────────────

class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", wt.USHORT),
        ("usUsage",     wt.USHORT),
        ("dwFlags",     wt.DWORD),
        ("hwndTarget",  wt.HWND),
    ]

class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType",  wt.DWORD),
        ("dwSize",  wt.DWORD),
        ("hDevice", wt.HANDLE),
        ("wParam",  wt.WPARAM),
    ]

class RAWMOUSE(ctypes.Structure):
    class _U(ctypes.Union):
        class _S(ctypes.Structure):
            _fields_ = [
                ("usButtonFlags", wt.USHORT),
                ("usButtonData",  wt.USHORT),
            ]
        _fields_ = [
            ("ulButtons", wt.ULONG),
            ("_s",        _S),
        ]
    _fields_ = [
        ("usFlags",            wt.USHORT),
        ("_u",                 _U),
        ("ulRawButtons",       wt.ULONG),
        ("lLastX",             wt.LONG),
        ("lLastY",             wt.LONG),
        ("ulExtraInformation", wt.ULONG),
    ]

class RAWINPUT(ctypes.Structure):
    class _DATA(ctypes.Union):
        _fields_ = [("mouse", RAWMOUSE)]
    _fields_ = [
        ("header", RAWINPUTHEADER),
        ("data",   _DATA),
    ]

# ── Recording state ───────────────────────────────────────────────────────────

class _State:
    recording     = False
    events        = []      # list of (perf_counter_s, dx, dy)
    lmb_down_at   = 0.0
    session_count = 0

_s = _State()

# Filled by main() from CLI args
_bucket_ms  = DEFAULT_BUCKET_MS
_output_dir = DEFAULT_OUTPUT_DIR
_weapon     = DEFAULT_WEAPON

# ── Bucketing & file save ─────────────────────────────────────────────────────

def _bucket(raw_events, bucket_ms):
    """Groups raw delta events into fixed-width time buckets (one per shot)."""
    if not raw_events:
        return []
    bucket_sec = bucket_ms / 1000.0
    t0         = raw_events[0][0]
    bucket_end = t0 + bucket_sec
    buckets    = []
    cx = cy    = 0
    for ts, dx, dy in raw_events:
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


def _save(raw_events):
    _s.session_count += 1
    buckets = _bucket(raw_events, _bucket_ms)

    if not buckets:
        print("[recorder] No movement detected — nothing saved.\n")
        return

    filename = f"{_weapon}_{_s.session_count:03d}.txt"
    filepath = os.path.join(_output_dir, filename)
    os.makedirs(_output_dir, exist_ok=True)

    with open(filepath, "w") as f:
        f.write("# x_offset, y_offset, delay_ms\n")
        f.write(f"# Recorded : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Weapon   : {_weapon}\n")
        f.write(f"# Shots    : {len(buckets)}\n")
        f.write(f"# Bucket   : {_bucket_ms} ms\n")
        f.write(f"# Raw evts : {len(raw_events)}\n#\n")
        for x, y, ms in buckets:
            f.write(f"{x}, {y}, {ms}\n")

    print(f"\n[recorder] ✓  Saved → {filepath}")
    print(f"           {len(buckets)} vectors from {len(raw_events)} raw delta events\n")
    print("  shot    x      y    ms")
    print("  " + "─" * 30)
    for i, (x, y, ms) in enumerate(buckets, 1):
        bx = ("→" * min(abs(x), 10)) if x > 0 else ("←" * min(abs(x), 10))
        by = ("↓" * min(abs(y), 10)) if y > 0 else ("↑" * min(abs(y), 10))
        print(f"  {i:<4}  {x:>5}  {y:>5}   {ms}   {bx}{by}")
    print()

# ── Window procedure ──────────────────────────────────────────────────────────

WNDPROCTYPE = ctypes.WINFUNCTYPE(
    ctypes.c_long, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM
)

def _wnd_proc(hwnd, msg, wparam, lparam):
    if msg == WM_INPUT:
        # Query required buffer size
        size = wt.UINT(0)
        user32.GetRawInputData(
            ctypes.cast(lparam, wt.HANDLE),
            RID_INPUT, None,
            ctypes.byref(size),
            ctypes.sizeof(RAWINPUTHEADER),
        )
        buf = (ctypes.c_byte * size.value)()
        user32.GetRawInputData(
            ctypes.cast(lparam, wt.HANDLE),
            RID_INPUT,
            ctypes.cast(buf, ctypes.c_void_p),
            ctypes.byref(size),
            ctypes.sizeof(RAWINPUTHEADER),
        )
        ri = ctypes.cast(buf, ctypes.POINTER(RAWINPUT)).contents

        # dwType == 0 means mouse
        if ri.header.dwType == 0:
            flags = ri.data.mouse._u._s.usButtonFlags

            if flags & RI_MOUSE_LEFT_BUTTON_DOWN:
                _s.recording   = True
                _s.events      = []
                _s.lmb_down_at = time.perf_counter()
                print("[recorder] ● Recording…  (release LMB to save)")

            elif flags & RI_MOUSE_LEFT_BUTTON_UP:
                _s.recording = False
                held_ms = (time.perf_counter() - _s.lmb_down_at) * 1000
                if held_ms < MIN_HOLD_MS:
                    print(f"[recorder] Click ignored ({held_ms:.0f} ms — too short)\n")
                else:
                    print(f"[recorder] ■ Stopped  ({held_ms:.0f} ms, {len(_s.events)} delta events)")
                    _save(_s.events)

            # Accumulate movement deltas while recording
            dx = ri.data.mouse.lLastX
            dy = ri.data.mouse.lLastY
            if _s.recording and (dx or dy):
                _s.events.append((time.perf_counter(), dx, dy))

        return 0

    if msg in (WM_DESTROY, WM_CLOSE):
        user32.PostQuitMessage(0)
        return 0

    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

# ── Window + Raw Input setup ──────────────────────────────────────────────────

def _create_window():
    """Creates an invisible message-only window to receive WM_INPUT events."""
    wnd_proc_cb = WNDPROCTYPE(_wnd_proc)
    _create_window._cb = wnd_proc_cb   # pin in memory — prevents GC

    hinstance  = kernel32.GetModuleHandleW(None)
    class_name = "CearumRawInputRecorder"

    class WNDCLASSEX(ctypes.Structure):
        _fields_ = [
            ("cbSize",        wt.UINT),
            ("style",         wt.UINT),
            ("lpfnWndProc",   WNDPROCTYPE),
            ("cbClsExtra",    ctypes.c_int),
            ("cbWndExtra",    ctypes.c_int),
            ("hInstance",     wt.HINSTANCE),
            ("hIcon",         wt.HICON),
            ("hCursor",       wt.HANDLE),
            ("hbrBackground", wt.HBRUSH),
            ("lpszMenuName",  wt.LPCWSTR),
            ("lpszClassName", wt.LPCWSTR),
            ("hIconSm",       wt.HICON),
        ]

    wcex = WNDCLASSEX()
    wcex.cbSize        = ctypes.sizeof(WNDCLASSEX)
    wcex.style         = CS_VREDRAW | CS_HREDRAW
    wcex.lpfnWndProc   = wnd_proc_cb
    wcex.hInstance     = hinstance
    wcex.lpszClassName = class_name

    user32.RegisterClassExW(ctypes.byref(wcex))

    # HWND_MESSAGE = invisible message-only window, no taskbar entry, no UI
    hwnd = user32.CreateWindowExW(
        0, class_name, "Cearum Recorder",
        WS_OVERLAPPED, 0, 0, 0, 0,
        HWND_MESSAGE, None, hinstance, None,
    )
    if not hwnd:
        raise RuntimeError(f"CreateWindowExW failed (err {kernel32.GetLastError()})")
    return hwnd


def _register_raw_input(hwnd):
    """Subscribes to mouse HID events via RegisterRawInputDevices."""
    rid = RAWINPUTDEVICE()
    rid.usUsagePage = HID_USAGE_PAGE_GENERIC
    rid.usUsage     = HID_USAGE_GENERIC_MOUSE
    rid.dwFlags     = RIDEV_INPUTSINK   # keep receiving while game has focus
    rid.hwndTarget  = hwnd

    ok = user32.RegisterRawInputDevices(
        ctypes.byref(rid), 1, ctypes.sizeof(RAWINPUTDEVICE)
    )
    if not ok:
        raise RuntimeError(f"RegisterRawInputDevices failed (err {kernel32.GetLastError()})")

# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    global _bucket_ms, _output_dir, _weapon

    parser = argparse.ArgumentParser(
        description="Cearum-Web recoil recorder — Win32 Raw Input, no hooks"
    )
    parser.add_argument("--weapon", "-w", default=DEFAULT_WEAPON,
                        help=f"Weapon name used in output filename (default: {DEFAULT_WEAPON})")
    parser.add_argument("--bucket", "-b", type=int, default=DEFAULT_BUCKET_MS,
                        help=f"Shot bucket size in ms, roughly 60000/RPM (default: {DEFAULT_BUCKET_MS})")
    parser.add_argument("--out", "-o", default=DEFAULT_OUTPUT_DIR,
                        help="Output directory for .txt files (default: current dir)")
    args = parser.parse_args()

    _bucket_ms  = args.bucket
    _output_dir = args.out
    _weapon     = args.weapon

    abs_out = os.path.abspath(_output_dir)

    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║       Cearum-Web  Recoil Recorder                ║")
    print("║       Win32 Raw Input — no hooks                 ║")
    print("╠══════════════════════════════════════════════════╣")
    print(f"║  Weapon  : {_weapon:<38}║")
    print(f"║  Bucket  : {str(_bucket_ms) + ' ms':<38}║")
    print(f"║  Output  : {abs_out[:38]:<38}║")
    print("╠══════════════════════════════════════════════════╣")
    print("║  ⚠  Turn Cearum recoil OFF before firing!       ║")
    print("║                                                  ║")
    print("║  Alt-tab into game → hold LMB to record          ║")
    print("║  Release LMB → .txt saved automatically          ║")
    print("║  Ctrl+C in this terminal → quit                  ║")
    print("╚══════════════════════════════════════════════════╝")
    print()

    try:
        hwnd = _create_window()
        _register_raw_input(hwnd)
    except RuntimeError as e:
        print(f"[error] {e}")
        sys.exit(1)

    print("[recorder] Listening — go fire in-game.\n")

    # Standard Win32 message loop — blocks until PostQuitMessage or Ctrl+C
    msg = wt.MSG()
    try:
        while True:
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret == 0 or ret == -1:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
    except KeyboardInterrupt:
        print("\n[recorder] Stopped.")

if __name__ == "__main__":
    main()
