package com.helix.companion.model

import com.google.gson.annotations.SerializedName

// WebSocket status broadcast (every 200 ms from server)
data class WsStatus(
    @SerializedName("makcu_connected") val makcuConnected: Boolean = false,
    @SerializedName("recoil_enabled") val recoilEnabled: Boolean = false,
    @SerializedName("flashlight_active") val flashlightActive: Boolean = false,
    @SerializedName("loaded_script") val loadedScript: String = "",
    @SerializedName("lmb_pressed") val lmbPressed: Boolean = false
)

// Full state from GET /api/state
data class FullState(
    val recoil: RecoilState = RecoilState(),
    val flashlight: FlashlightState = FlashlightState(),
    val settings: SettingsState = SettingsState()
)

data class RecoilState(
    val enabled: Boolean = false,
    @SerializedName("toggle_keybind") val toggleKeybind: String = "NONE",
    @SerializedName("cycle_keybind") val cycleKeybind: String = "NONE",
    @SerializedName("require_aim") val requireAim: Boolean = false,
    val loop: Boolean = false,
    val randomise: Boolean = false,
    @SerializedName("return_crosshair") val returnCrosshair: Boolean = false,
    @SerializedName("recoil_scalar") val recoilScalar: Float = 1.0f,
    @SerializedName("x_control") val xControl: Float = 1.0f,
    @SerializedName("y_control") val yControl: Float = 1.0f,
    @SerializedName("randomisation_strength") val randomisationStrength: Float = 0.0f,
    @SerializedName("return_speed") val returnSpeed: Float = 1.0f,
    @SerializedName("loaded_script") val loadedScript: String = ""
)

data class FlashlightState(
    val enabled: Boolean = false,
    val keybind: String = "NONE",
    @SerializedName("hold_threshold_ms") val holdThresholdMs: Int = 500,
    @SerializedName("cooldown_ms") val cooldownMs: Int = 2000,
    @SerializedName("pre_fire_min_ms") val preFireMinMs: Int = 0,
    @SerializedName("pre_fire_max_ms") val preFireMaxMs: Int = 0
)

data class SettingsState(
    val game: String = "Manual",
    val sensitivity: Float = 1.0f
)

// Script list response from GET /api/scripts
data class ScriptListResponse(
    val scripts: List<String> = emptyList()
)

// Games list from GET /api/scripts/games
data class GamesListResponse(
    val games: List<String> = emptyList()
)

// POST body helpers
data class RecoilToggleBody(val enabled: Boolean)
data class FlashlightToggleBody(val enabled: Boolean)

data class RecoilUpdateBody(
    @SerializedName("toggle_keybind") val toggleKeybind: String? = null,
    @SerializedName("cycle_keybind") val cycleKeybind: String? = null,
    @SerializedName("require_aim") val requireAim: Boolean? = null,
    val loop: Boolean? = null,
    val randomise: Boolean? = null,
    @SerializedName("return_crosshair") val returnCrosshair: Boolean? = null,
    @SerializedName("recoil_scalar") val recoilScalar: Float? = null,
    @SerializedName("x_control") val xControl: Float? = null,
    @SerializedName("y_control") val yControl: Float? = null,
    @SerializedName("randomisation_strength") val randomisationStrength: Float? = null,
    @SerializedName("return_speed") val returnSpeed: Float? = null
)

data class FlashlightUpdateBody(
    val keybind: String? = null,
    @SerializedName("hold_threshold_ms") val holdThresholdMs: Int? = null,
    @SerializedName("cooldown_ms") val cooldownMs: Int? = null,
    @SerializedName("pre_fire_min_ms") val preFireMinMs: Int? = null,
    @SerializedName("pre_fire_max_ms") val preFireMaxMs: Int? = null
)

data class SettingsUpdateBody(
    val game: String? = null,
    val sensitivity: Float? = null
)

// UI state exposed from ViewModel
data class HelixUiState(
    val wsConnected: Boolean = false,
    val makcuConnected: Boolean = false,
    val recoilEnabled: Boolean = false,
    val flashlightActive: Boolean = false,
    val loadedScript: String = "",
    val lmbPressed: Boolean = false,
    val recoil: RecoilState = RecoilState(),
    val flashlight: FlashlightState = FlashlightState(),
    val settings: SettingsState = SettingsState(),
    val scripts: List<String> = emptyList(),
    val games: List<String> = emptyList(),
    val serverHost: String = "",
    val fullStateLoaded: Boolean = false,
    val error: String? = null
)
