package com.helix.companion.ui.theme

import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

val HelixBlue = Color(0xFF4D9CFF)
val HelixBlueDim = Color(0xFF1A3A66)
val HelixGreen = Color(0xFF4CAF50)
val HelixGreenDim = Color(0xFF1B3D1E)
val HelixRed = Color(0xFFE53935)
val HelixBackground = Color(0xFF0D0D0D)
val HelixSurface = Color(0xFF1A1A1A)
val HelixSurfaceVariant = Color(0xFF242424)
val HelixOnSurface = Color(0xFFE0E0E0)
val HelixOnSurfaceDim = Color(0xFF888888)

private val HelixColorScheme = darkColorScheme(
    primary = HelixBlue,
    onPrimary = Color.Black,
    primaryContainer = HelixBlueDim,
    onPrimaryContainer = HelixBlue,
    secondary = HelixGreen,
    onSecondary = Color.Black,
    background = HelixBackground,
    onBackground = HelixOnSurface,
    surface = HelixSurface,
    onSurface = HelixOnSurface,
    surfaceVariant = HelixSurfaceVariant,
    onSurfaceVariant = HelixOnSurfaceDim,
    outline = Color(0xFF333333),
    error = HelixRed,
    onError = Color.White
)

@Composable
fun HelixTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = HelixColorScheme,
        typography = Typography(),
        content = content
    )
}
