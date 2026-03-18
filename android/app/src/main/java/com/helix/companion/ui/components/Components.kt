package com.helix.companion.ui.components

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.helix.companion.ui.theme.*

// Large toggle card for home screen (Recoil / Flashlight)
@Composable
fun BigToggleCard(
    label: String,
    isOn: Boolean,
    icon: ImageVector,
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    val bgColor by animateColorAsState(
        targetValue = if (isOn) HelixGreenDim else HelixSurface,
        animationSpec = tween(200), label = "bg"
    )
    val borderColor by animateColorAsState(
        targetValue = if (isOn) HelixGreen else Color(0xFF333333),
        animationSpec = tween(200), label = "border"
    )
    val labelColor by animateColorAsState(
        targetValue = if (isOn) HelixGreen else HelixOnSurfaceDim,
        animationSpec = tween(200), label = "label"
    )

    Box(
        modifier = modifier
            .clip(RoundedCornerShape(16.dp))
            .background(bgColor)
            .border(1.5.dp, borderColor, RoundedCornerShape(16.dp))
            .clickable(onClick = onClick)
            .padding(16.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
            Icon(
                imageVector = icon,
                contentDescription = label,
                tint = labelColor,
                modifier = Modifier.size(36.dp)
            )
            Spacer(Modifier.height(8.dp))
            Text(
                text = label,
                color = HelixOnSurface,
                fontWeight = FontWeight.Bold,
                fontSize = 15.sp
            )
            Spacer(Modifier.height(4.dp))
            Text(
                text = if (isOn) "ON" else "OFF",
                color = labelColor,
                fontWeight = FontWeight.ExtraBold,
                fontSize = 20.sp
            )
        }
    }
}

// Status dot in header
@Composable
fun StatusDot(connected: Boolean, label: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(
            modifier = Modifier
                .size(8.dp)
                .clip(CircleShape)
                .background(if (connected) HelixGreen else HelixRed)
        )
        Spacer(Modifier.width(4.dp))
        Text(label, color = HelixOnSurfaceDim, fontSize = 12.sp)
    }
}

// Section card container
@Composable
fun SectionCard(
    title: String,
    modifier: Modifier = Modifier,
    content: @Composable ColumnScope.() -> Unit
) {
    Column(
        modifier = modifier
            .clip(RoundedCornerShape(12.dp))
            .background(HelixSurface)
            .padding(16.dp)
    ) {
        Text(
            text = title,
            color = HelixBlue,
            fontWeight = FontWeight.Bold,
            fontSize = 13.sp,
            letterSpacing = 1.sp
        )
        Spacer(Modifier.height(12.dp))
        content()
    }
}

// Labelled slider row
@Composable
fun LabelledSlider(
    label: String,
    value: Float,
    valueRange: ClosedFloatingPointRange<Float>,
    steps: Int = 0,
    onValueChangeFinished: (Float) -> Unit,
    displayValue: String = "%.2f".format(value)
) {
    var sliderValue by remember(value) { mutableFloatStateOf(value) }

    Column {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(label, color = HelixOnSurface, fontSize = 13.sp)
            Text(displayValue, color = HelixBlue, fontSize = 13.sp, fontWeight = FontWeight.Bold)
        }
        Slider(
            value = sliderValue,
            onValueChange = { sliderValue = it },
            onValueChangeFinished = { onValueChangeFinished(sliderValue) },
            valueRange = valueRange,
            steps = steps,
            colors = SliderDefaults.colors(
                thumbColor = HelixBlue,
                activeTrackColor = HelixBlue,
                inactiveTrackColor = HelixSurfaceVariant
            ),
            modifier = Modifier.fillMaxWidth()
        )
    }
}

// Toggle row (label + switch)
@Composable
fun ToggleRow(label: String, checked: Boolean, onCheckedChange: (Boolean) -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(label, color = HelixOnSurface, fontSize = 14.sp)
        Switch(
            checked = checked,
            onCheckedChange = onCheckedChange,
            colors = SwitchDefaults.colors(
                checkedThumbColor = Color.White,
                checkedTrackColor = HelixGreen,
                uncheckedThumbColor = HelixOnSurfaceDim,
                uncheckedTrackColor = HelixSurfaceVariant
            )
        )
    }
}

// Keybind dropdown row
@Composable
fun KeybindRow(label: String, value: String, options: List<String>, onSelect: (String) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(label, color = HelixOnSurface, fontSize = 14.sp, modifier = Modifier.weight(1f))
        Box {
            OutlinedButton(
                onClick = { expanded = true },
                colors = ButtonDefaults.outlinedButtonColors(contentColor = HelixBlue),
                border = androidx.compose.foundation.BorderStroke(1.dp, HelixBlueDim)
            ) {
                Text(value, fontSize = 13.sp)
            }
            DropdownMenu(
                expanded = expanded,
                onDismissRequest = { expanded = false },
                modifier = Modifier.background(HelixSurfaceVariant)
            ) {
                options.forEach { opt ->
                    DropdownMenuItem(
                        text = { Text(opt, color = if (opt == value) HelixBlue else HelixOnSurface) },
                        onClick = { onSelect(opt); expanded = false }
                    )
                }
            }
        }
    }
}
