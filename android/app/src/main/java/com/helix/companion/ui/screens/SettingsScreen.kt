package com.helix.companion.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.helix.companion.model.HelixUiState
import com.helix.companion.ui.components.*
import com.helix.companion.ui.theme.*

private val GAME_PRESETS = listOf(
    "Manual",
    "Arena Breakout Infinite",
    "CS2",
    "Gray Zone Warfare",
    "Hunt: Showdown",
    "Marathon",
    "Marvel Rivals",
    "PUBG: Battlegrounds",
    "Valorant"
)

@Composable
fun SettingsScreen(
    state: HelixUiState,
    onGameChanged: (String) -> Unit,
    onSensitivityChanged: (Float) -> Unit,
    onHostChanged: (String) -> Unit
) {
    val focusManager = LocalFocusManager.current
    var hostInput by remember(state.serverHost) { mutableStateOf(state.serverHost) }
    var sensInput by remember(state.settings.sensitivity) {
        mutableStateOf("%.2f".format(state.settings.sensitivity))
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        // Server connection
        SectionCard(title = "CONNECTION") {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column {
                    StatusDot(connected = state.wsConnected, label = "WebSocket")
                    Spacer(Modifier.height(4.dp))
                    StatusDot(connected = state.makcuConnected, label = "MAKCU")
                }
            }
            Spacer(Modifier.height(12.dp))
            OutlinedTextField(
                value = hostInput,
                onValueChange = { hostInput = it },
                label = { Text("Server address  (e.g. 192.168.1.10:8000)", fontSize = 12.sp) },
                singleLine = true,
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Uri,
                    imeAction = ImeAction.Done
                ),
                keyboardActions = KeyboardActions(onDone = {
                    focusManager.clearFocus()
                    if (hostInput.isNotBlank()) onHostChanged(hostInput.trim())
                }),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = HelixBlue,
                    unfocusedBorderColor = HelixSurfaceVariant,
                    focusedTextColor = HelixOnSurface,
                    unfocusedTextColor = HelixOnSurface,
                    cursorColor = HelixBlue
                ),
                modifier = Modifier.fillMaxWidth()
            )
            Spacer(Modifier.height(8.dp))
            Button(
                onClick = {
                    focusManager.clearFocus()
                    if (hostInput.isNotBlank()) onHostChanged(hostInput.trim())
                },
                colors = ButtonDefaults.buttonColors(containerColor = HelixBlue),
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("Connect", color = HelixBackground)
            }
        }

        // Sensitivity scaling
        SectionCard(title = "SENSITIVITY SCALING") {
            KeybindRow(
                label = "Game Preset",
                value = state.settings.game,
                options = GAME_PRESETS,
                onSelect = onGameChanged
            )
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(
                value = sensInput,
                onValueChange = { sensInput = it },
                label = { Text("In-Game Sensitivity", fontSize = 12.sp) },
                singleLine = true,
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Decimal,
                    imeAction = ImeAction.Done
                ),
                keyboardActions = KeyboardActions(onDone = {
                    focusManager.clearFocus()
                    sensInput.toFloatOrNull()?.let { onSensitivityChanged(it) }
                }),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = HelixBlue,
                    unfocusedBorderColor = HelixSurfaceVariant,
                    focusedTextColor = HelixOnSurface,
                    unfocusedTextColor = HelixOnSurface,
                    cursorColor = HelixBlue
                ),
                modifier = Modifier.fillMaxWidth()
            )
        }
    }
}
