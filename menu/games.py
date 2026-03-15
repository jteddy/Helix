# Single source of truth for all game definitions.
# To add a new game: add it to GAME_BASE_SENSITIVITIES with its recorded base sensitivity.
# Everything else (dropdown list, scaling logic) is derived automatically.

MANUAL = "Manual"

# Per-game base sensitivity — the sensitivity each game's scripts were recorded at.
# Update a value here if scripts for that game were recorded at a different sensitivity.
GAME_BASE_SENSITIVITIES = {
    "Arena Breakout Infinite": 1.0,
    "CS2":                     1.25,
    "Gray Zone Warfare":       1.0,
    "Hunt: Showdown":          1.0,
    "Marathon":                1.0,
    "Marvel Rivals":           1.0,
    "PUBG: Battlegrounds":     1.0,
    "Valorant":                1.0,
}

# Derived — do not edit below this line
ALL_GAMES = sorted(GAME_BASE_SENSITIVITIES.keys()) + [MANUAL]
