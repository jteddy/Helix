package com.helix.companion.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.FlashlightOn
import androidx.compose.material.icons.filled.TrackChanges
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.helix.companion.model.HelixUiState
import com.helix.companion.ui.components.BigToggleCard
import com.helix.companion.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    state: HelixUiState,
    onToggleRecoil: () -> Unit,
    onToggleFlashlight: () -> Unit,
    onScriptSelected: (String, String?) -> Unit
) {
    var showScriptPicker by remember { mutableStateOf(false) }
    var selectedGame by remember { mutableStateOf<String?>(null) }

    BoxWithConstraints(modifier = Modifier.fillMaxSize()) {
        val isLandscape = maxWidth > maxHeight

        if (isLandscape) {
            LandscapeHome(state, onToggleRecoil, onToggleFlashlight) { showScriptPicker = true }
        } else {
            PortraitHome(state, onToggleRecoil, onToggleFlashlight) { showScriptPicker = true }
        }
    }

    // Script picker bottom sheet
    if (showScriptPicker) {
        ScriptPickerSheet(
            games = state.games,
            scripts = state.scripts,
            currentScript = state.loadedScript,
            selectedGame = selectedGame,
            onGameSelected = { selectedGame = it },
            onScriptSelected = { name ->
                onScriptSelected(name, selectedGame)
                showScriptPicker = false
            },
            onDismiss = { showScriptPicker = false }
        )
    }
}

@Composable
private fun PortraitHome(
    state: HelixUiState,
    onToggleRecoil: () -> Unit,
    onToggleFlashlight: () -> Unit,
    onOpenScriptPicker: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        // Toggle cards — fill most of the height
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f),
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            BigToggleCard(
                label = "RECOIL",
                isOn = state.recoilEnabled,
                icon = Icons.Default.TrackChanges,
                modifier = Modifier
                    .weight(1f)
                    .fillMaxHeight(),
                onClick = onToggleRecoil
            )
            BigToggleCard(
                label = "FLASHLIGHT",
                isOn = state.flashlightActive,
                icon = Icons.Default.FlashlightOn,
                modifier = Modifier
                    .weight(1f)
                    .fillMaxHeight(),
                onClick = onToggleFlashlight
            )
        }

        // Script card
        ScriptCard(
            scriptName = state.loadedScript,
            modifier = Modifier.fillMaxWidth(),
            onClick = onOpenScriptPicker
        )
    }
}

@Composable
private fun LandscapeHome(
    state: HelixUiState,
    onToggleRecoil: () -> Unit,
    onToggleFlashlight: () -> Unit,
    onOpenScriptPicker: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        BigToggleCard(
            label = "RECOIL",
            isOn = state.recoilEnabled,
            icon = Icons.Default.TrackChanges,
            modifier = Modifier
                .weight(1f)
                .fillMaxHeight(),
            onClick = onToggleRecoil
        )
        BigToggleCard(
            label = "FLASHLIGHT",
            isOn = state.flashlightActive,
            icon = Icons.Default.FlashlightOn,
            modifier = Modifier
                .weight(1f)
                .fillMaxHeight(),
            onClick = onToggleFlashlight
        )
        ScriptCard(
            scriptName = state.loadedScript,
            modifier = Modifier
                .weight(1f)
                .fillMaxHeight(),
            onClick = onOpenScriptPicker
        )
    }
}

@Composable
private fun ScriptCard(scriptName: String, modifier: Modifier = Modifier, onClick: () -> Unit) {
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(16.dp))
            .background(HelixSurface)
            .border(1.5.dp, HelixBlueDim, RoundedCornerShape(16.dp))
            .clickable(onClick = onClick)
            .padding(16.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text("SCRIPT", color = HelixOnSurfaceDim, fontSize = 12.sp, letterSpacing = 1.sp)
            Spacer(Modifier.height(8.dp))
            Text(
                text = scriptName.ifBlank { "None" },
                color = HelixBlue,
                fontWeight = FontWeight.Bold,
                fontSize = 16.sp,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis
            )
            Spacer(Modifier.height(6.dp))
            Text("TAP TO CHANGE", color = HelixOnSurfaceDim, fontSize = 11.sp, letterSpacing = 0.5.sp)
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ScriptPickerSheet(
    games: List<String>,
    scripts: List<String>,
    currentScript: String,
    selectedGame: String?,
    onGameSelected: (String?) -> Unit,
    onScriptSelected: (String) -> Unit,
    onDismiss: () -> Unit
) {
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        containerColor = HelixSurface,
        dragHandle = { BottomSheetDefaults.DragHandle(color = HelixOnSurfaceDim) }
    ) {
        Column(modifier = Modifier.padding(horizontal = 16.dp).padding(bottom = 32.dp)) {
            Text(
                "Select Script",
                color = HelixOnSurface,
                fontWeight = FontWeight.Bold,
                fontSize = 18.sp,
                modifier = Modifier.padding(bottom = 16.dp)
            )

            // Game filter chips
            if (games.isNotEmpty()) {
                ScrollableTabRow(
                    selectedTabIndex = if (selectedGame == null) 0 else games.indexOf(selectedGame) + 1,
                    containerColor = HelixSurface,
                    contentColor = HelixBlue,
                    edgePadding = 0.dp,
                    modifier = Modifier.padding(bottom = 12.dp)
                ) {
                    Tab(
                        selected = selectedGame == null,
                        onClick = { onGameSelected(null) },
                        text = { Text("All") }
                    )
                    games.forEach { game ->
                        Tab(
                            selected = selectedGame == game,
                            onClick = { onGameSelected(game) },
                            text = { Text(game) }
                        )
                    }
                }
            }

            // Script list
            if (scripts.isEmpty()) {
                Box(modifier = Modifier.fillMaxWidth().padding(32.dp), contentAlignment = Alignment.Center) {
                    Text("No scripts found", color = HelixOnSurfaceDim)
                }
            } else {
                scripts.forEach { script ->
                    val isCurrent = script == currentScript || script.endsWith("/$currentScript")
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(8.dp))
                            .background(if (isCurrent) HelixBlueDim else HelixSurfaceVariant)
                            .clickable { onScriptSelected(script) }
                            .padding(horizontal = 16.dp, vertical = 14.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = script,
                            color = if (isCurrent) HelixBlue else HelixOnSurface,
                            fontWeight = if (isCurrent) FontWeight.Bold else FontWeight.Normal,
                            fontSize = 15.sp
                        )
                    }
                    Spacer(Modifier.height(4.dp))
                }
            }
        }
    }
}
