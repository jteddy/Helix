package com.helix.companion.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.helix.companion.model.HelixUiState
import com.helix.companion.ui.components.*

private val KEYBIND_OPTIONS = listOf("NONE", "M4", "M5", "MMB")

@Composable
fun RecoilScreen(
    state: HelixUiState,
    onToggleKeybind: (String) -> Unit,
    onCycleKeybind: (String) -> Unit,
    onRequireAim: (Boolean) -> Unit,
    onLoop: (Boolean) -> Unit,
    onRandomise: (Boolean) -> Unit,
    onReturnCrosshair: (Boolean) -> Unit,
    onRecoilScalar: (Float) -> Unit,
    onXControl: (Float) -> Unit,
    onYControl: (Float) -> Unit,
    onRandomisationStrength: (Float) -> Unit,
    onReturnSpeed: (Float) -> Unit
) {
    val recoil = state.recoil

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        // Control card
        SectionCard(title = "CONTROL") {
            ToggleRow("Require Aim (RMB)", recoil.requireAim, onRequireAim)
            ToggleRow("Loop Recoil", recoil.loop, onLoop)
            ToggleRow("Randomisation", recoil.randomise, onRandomise)
            ToggleRow("Return Crosshair", recoil.returnCrosshair, onReturnCrosshair)
            Spacer(Modifier.height(4.dp))
            KeybindRow("Toggle Keybind", recoil.toggleKeybind, KEYBIND_OPTIONS, onToggleKeybind)
            KeybindRow("Cycle Script Keybind", recoil.cycleKeybind, KEYBIND_OPTIONS, onCycleKeybind)
        }

        // Scaling card
        SectionCard(title = "SCALING") {
            LabelledSlider(
                label = "Recoil Scalar",
                value = recoil.recoilScalar,
                valueRange = 0f..5f,
                onValueChangeFinished = onRecoilScalar
            )
            Spacer(Modifier.height(4.dp))
            LabelledSlider(
                label = "X Control",
                value = recoil.xControl,
                valueRange = 0f..1f,
                onValueChangeFinished = onXControl
            )
            Spacer(Modifier.height(4.dp))
            LabelledSlider(
                label = "Y Control",
                value = recoil.yControl,
                valueRange = 0f..1f,
                onValueChangeFinished = onYControl
            )
            Spacer(Modifier.height(4.dp))
            LabelledSlider(
                label = "Randomisation Strength",
                value = recoil.randomisationStrength,
                valueRange = 0f..3f,
                onValueChangeFinished = onRandomisationStrength
            )
            Spacer(Modifier.height(4.dp))
            LabelledSlider(
                label = "Return Speed",
                value = recoil.returnSpeed,
                valueRange = 0f..2f,
                onValueChangeFinished = onReturnSpeed
            )
        }
    }
}
