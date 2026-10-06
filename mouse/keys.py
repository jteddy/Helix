"""Keyboard key names for km.press, from the vendor's KM_API key table (mak-suite
protocol/KM_API.md, "Key arguments"). Names map to USB HID keyboard usages; Helix sends
the number, which the firmware accepts unambiguously. normalize_key() returns the
canonical name stored in settings (aliases such as 'ctrl' or 'esc' are folded in)."""

_NAMED = {
    40: ("enter", "return"),
    41: ("escape", "esc"),
    42: ("backspace", "back"),
    43: ("tab",),
    44: ("space", "spacebar"),
    45: ("minus", "dash", "hyphen"),
    46: ("equals", "equal"),
    47: ("leftbracket", "lbracket", "openbracket"),
    48: ("rightbracket", "rbracket", "closebracket"),
    49: ("backslash", "bslash"),
    50: ("nonus_hash",),
    51: ("semicolon", "semi"),
    52: ("quote", "apostrophe", "singlequote"),
    53: ("grave", "backtick", "tilde"),
    54: ("comma",),
    55: ("period", "dot"),
    56: ("slash", "forwardslash", "fslash"),
    57: ("capslock", "caps"),
    70: ("printscreen", "prtsc", "print"),
    71: ("scrolllock", "scroll"),
    72: ("pause", "break"),
    73: ("insert", "ins"),
    74: ("home",),
    75: ("pageup", "pgup"),
    76: ("delete", "del"),
    77: ("end",),
    78: ("pagedown", "pgdown", "pgdn"),
    79: ("right", "rightarrow"),
    80: ("left", "leftarrow"),
    81: ("down", "downarrow"),
    82: ("up", "uparrow"),
    83: ("numlock", "num"),
    84: ("kpdivide", "npdivide"),
    85: ("kpmultiply", "npmultiply"),
    86: ("kpminus", "npminus"),
    87: ("kpplus", "npplus"),
    88: ("kpenter", "npenter"),
    99: ("kpperiod", "kpdot", "npperiod", "npdot"),
    224: ("leftctrl", "lctrl", "leftcontrol", "lcontrol", "ctrl", "control"),
    225: ("leftshift", "lshift", "shift"),
    226: ("leftalt", "lalt", "alt"),
    227: ("leftgui", "lgui", "leftwin", "lwin", "gui", "win", "windows", "super", "meta", "cmd", "command"),
    228: ("rightctrl", "rctrl", "rightcontrol", "rcontrol"),
    229: ("rightshift", "rshift"),
    230: ("rightalt", "ralt"),
    231: ("rightgui", "rgui", "rightwin", "rwin", "rightwindows"),
}

_CANON = {}   # alias -> canonical name
_USAGE = {}   # canonical name -> HID usage
for _u, _names in _NAMED.items():
    _USAGE[_names[0]] = _u
    for _n in _names:
        _CANON[_n] = _names[0]
for _i, _c in enumerate("abcdefghijklmnopqrstuvwxyz"):
    _USAGE[_c] = 4 + _i
for _i, _c in enumerate("1234567890"):
    _USAGE[_c] = 30 + _i
for _i in range(1, 13):
    _USAGE[f"f{_i}"] = 57 + _i
for _i in range(1, 10):
    _USAGE[f"kp{_i}"] = 88 + _i
    _CANON[f"np{_i}"] = f"kp{_i}"
_USAGE["kp0"] = 98
_CANON["np0"] = "kp0"
for _n in _USAGE:
    _CANON.setdefault(_n, _n)


def normalize_key(name):
    """Canonical key name, or None if the firmware has no such key name."""
    if not isinstance(name, str):
        return None
    return _CANON.get(name.strip().strip("'\"").strip().lower())


def key_usage(name):
    """USB HID usage for a key name (any alias), or None."""
    canon = normalize_key(name)
    return _USAGE[canon] if canon else None
