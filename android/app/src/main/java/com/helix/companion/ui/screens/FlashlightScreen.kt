package com.helix.companion.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.helix.companion.model.HelixUiState
import com.helix.companion.ui.components.*

private val FL_KEYBIND_OPTIONS = listOf("NONE", "LMB", "RMB", "MMB", "M4", "M5")

@Composable
fun FlashlightScreen(
    state: HelixUiState,
    onKeybind: (String) -> Unit,
    onHoldThreshold: (Int) -> Unit,
    onCooldown: (Int) -> Unit,
    onPreFireMin: (Int) -> Unit,
    onPreFireMax: (Int) -> Unit
) {
    val fl = state.flashlight

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        // Control card
        SectionCard(title = "CONTROL") {
            KeybindRow("Flashlight Key", fl.keybind, FL_KEYBIND_OPTIONS, onKeybind)
        }

        // Timing card
        SectionCard(title = "TIMING") {
            LabelledSlider(
                label = "Hold Threshold",
                value = fl.holdThresholdMs.toFloat(),
                valueRange = 0f..2000f,
                onValueChangeFinished = { onHoldThreshold(it.toInt()) },
                displayValue = "${fl.holdThresholdMs} ms"
            )
            Spacer(Modifier.height(4.dp))
            LabelledSlider(
                label = "Cooldown",
                value = fl.cooldownMs.toFloat(),
                valueRange = 0f..10000f,
                onValueChangeFinished = { onCooldown(it.toInt()) },
                displayValue = "${fl.cooldownMs} ms"
            )
            Spacer(Modifier.height(4.dp))
            LabelledSlider(
                label = "Pre-Fire Delay Min",
                value = fl.preFireMinMs.toFloat(),
                valueRange = 0f..1000f,
                onValueChangeFinished = { onPreFireMin(it.toInt()) },
                displayValue = "${fl.preFireMinMs} ms"
            )
            Spacer(Modifier.height(4.dp))
            LabelledSlider(
                label = "Pre-Fire Delay Max",
                value = fl.preFireMaxMs.toFloat(),
                valueRange = 0f..1000f,
                onValueChangeFinished = { onPreFireMax(it.toInt()) },
                displayValue = "${fl.preFireMaxMs} ms"
            )
        }
    }
}
