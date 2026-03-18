package com.helix.companion.viewmodel

import android.app.Application
import android.content.Context
import android.content.Intent
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.helix.companion.api.HelixApi
import com.helix.companion.model.*
import com.helix.companion.service.WebSocketService
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch

private val Context.dataStore by preferencesDataStore("helix_prefs")
private val KEY_HOST = stringPreferencesKey("server_host")

class HelixViewModel(application: Application) : AndroidViewModel(application) {

    private val ctx = application.applicationContext
    private val _uiState = MutableStateFlow(HelixUiState())
    val uiState: StateFlow<HelixUiState> = _uiState.asStateFlow()

    private var api: HelixApi? = null

    init {
        // Restore saved host and kick off connection
        viewModelScope.launch {
            ctx.dataStore.data.first()[KEY_HOST]?.let { saved ->
                if (saved.isNotBlank()) applyHost(saved)
            }
        }
        // Observe WebSocket status broadcasts
        viewModelScope.launch {
            WebSocketService.statusFlow.collect { ws ->
                _uiState.update {
                    it.copy(
                        makcuConnected = ws.makcuConnected,
                        recoilEnabled = ws.recoilEnabled,
                        flashlightActive = ws.flashlightActive,
                        loadedScript = ws.loadedScript,
                        lmbPressed = ws.lmbPressed
                    )
                }
            }
        }
        viewModelScope.launch {
            WebSocketService.connectedFlow.collect { connected ->
                _uiState.update { it.copy(wsConnected = connected) }
            }
        }
    }

    // ---- Host management ----

    fun setHost(host: String) {
        viewModelScope.launch {
            ctx.dataStore.edit { it[KEY_HOST] = host }
            applyHost(host)
        }
    }

    private fun applyHost(host: String) {
        api = HelixApi(host)
        _uiState.update { it.copy(serverHost = host, fullStateLoaded = false, error = null) }
        // Start/update the foreground service
        val intent = Intent(ctx, WebSocketService::class.java).apply {
            action = WebSocketService.ACTION_SET_HOST
            putExtra(WebSocketService.EXTRA_HOST, host)
        }
        ctx.startForegroundService(intent)
        loadFullState()
    }

    // ---- Full state load ----

    fun loadFullState() {
        val a = api ?: return
        viewModelScope.launch(Dispatchers.IO) {
            runCatching { a.getFullState() }.onSuccess { state ->
                _uiState.update {
                    it.copy(
                        recoil = state.recoil,
                        flashlight = state.flashlight,
                        settings = state.settings,
                        recoilEnabled = state.recoil.enabled,
                        loadedScript = state.recoil.loadedScript,
                        fullStateLoaded = true,
                        error = null
                    )
                }
                loadScripts()
            }.onFailure { e ->
                _uiState.update { it.copy(error = "Cannot reach server: ${e.message}") }
            }
        }
    }

    private suspend fun loadScripts() {
        val a = api ?: return
        runCatching {
            val games = a.getGames()
            val scripts = a.getScripts()
            _uiState.update { it.copy(games = games, scripts = scripts) }
        }
    }

    // ---- Toggles ----

    fun toggleRecoil() {
        val a = api ?: return
        viewModelScope.launch(Dispatchers.IO) {
            runCatching { a.toggleRecoil() }
        }
    }

    fun toggleFlashlight() {
        val a = api ?: return
        viewModelScope.launch(Dispatchers.IO) {
            runCatching { a.toggleFlashlight() }
        }
    }

    // ---- Script selection ----

    fun loadScript(name: String, game: String? = null) {
        val a = api ?: return
        viewModelScope.launch(Dispatchers.IO) {
            runCatching { a.loadScript(name, game) }
        }
    }

    fun loadScriptsForGame(game: String?) {
        val a = api ?: return
        viewModelScope.launch(Dispatchers.IO) {
            runCatching {
                val scripts = a.getScripts(game)
                _uiState.update { it.copy(scripts = scripts) }
            }
        }
    }

    // ---- Recoil settings ----

    fun updateRecoilScalar(value: Float) = updateRecoil { copy(recoilScalar = value) }
    fun updateXControl(value: Float) = updateRecoil { copy(xControl = value) }
    fun updateYControl(value: Float) = updateRecoil { copy(yControl = value) }
    fun updateRandomisationStrength(value: Float) = updateRecoil { copy(randomisationStrength = value) }
    fun updateReturnSpeed(value: Float) = updateRecoil { copy(returnSpeed = value) }
    fun updateRequireAim(value: Boolean) = updateRecoil { copy(requireAim = value) }
    fun updateLoop(value: Boolean) = updateRecoil { copy(loop = value) }
    fun updateRandomise(value: Boolean) = updateRecoil { copy(randomise = value) }
    fun updateReturnCrosshair(value: Boolean) = updateRecoil { copy(returnCrosshair = value) }
    fun updateToggleKeybind(value: String) = updateRecoil { copy(toggleKeybind = value) }
    fun updateCycleKeybind(value: String) = updateRecoil { copy(cycleKeybind = value) }

    private fun updateRecoil(transform: RecoilState.() -> RecoilState) {
        val newRecoil = _uiState.value.recoil.transform()
        _uiState.update { it.copy(recoil = newRecoil) }
        val a = api ?: return
        val body = RecoilUpdateBody(
            toggleKeybind = newRecoil.toggleKeybind,
            cycleKeybind = newRecoil.cycleKeybind,
            requireAim = newRecoil.requireAim,
            loop = newRecoil.loop,
            randomise = newRecoil.randomise,
            returnCrosshair = newRecoil.returnCrosshair,
            recoilScalar = newRecoil.recoilScalar,
            xControl = newRecoil.xControl,
            yControl = newRecoil.yControl,
            randomisationStrength = newRecoil.randomisationStrength,
            returnSpeed = newRecoil.returnSpeed
        )
        viewModelScope.launch(Dispatchers.IO) { runCatching { a.updateRecoil(body) } }
    }

    // ---- Flashlight settings ----

    fun updateFlashlightKeybind(value: String) = updateFlashlight { copy(keybind = value) }
    fun updateHoldThreshold(value: Int) = updateFlashlight { copy(holdThresholdMs = value) }
    fun updateCooldown(value: Int) = updateFlashlight { copy(cooldownMs = value) }
    fun updatePreFireMin(value: Int) = updateFlashlight { copy(preFireMinMs = value) }
    fun updatePreFireMax(value: Int) = updateFlashlight { copy(preFireMaxMs = value) }

    private fun updateFlashlight(transform: FlashlightState.() -> FlashlightState) {
        val newFl = _uiState.value.flashlight.transform()
        _uiState.update { it.copy(flashlight = newFl) }
        val a = api ?: return
        val body = FlashlightUpdateBody(
            keybind = newFl.keybind,
            holdThresholdMs = newFl.holdThresholdMs,
            cooldownMs = newFl.cooldownMs,
            preFireMinMs = newFl.preFireMinMs,
            preFireMaxMs = newFl.preFireMaxMs
        )
        viewModelScope.launch(Dispatchers.IO) { runCatching { a.updateFlashlight(body) } }
    }

    // ---- Settings ----

    fun updateGame(game: String) {
        val newSettings = _uiState.value.settings.copy(game = game)
        _uiState.update { it.copy(settings = newSettings) }
        val a = api ?: return
        viewModelScope.launch(Dispatchers.IO) {
            runCatching { a.updateSettings(SettingsUpdateBody(game = game)) }
        }
    }

    fun updateSensitivity(sensitivity: Float) {
        val newSettings = _uiState.value.settings.copy(sensitivity = sensitivity)
        _uiState.update { it.copy(settings = newSettings) }
        val a = api ?: return
        viewModelScope.launch(Dispatchers.IO) {
            runCatching { a.updateSettings(SettingsUpdateBody(sensitivity = sensitivity)) }
        }
    }
}
