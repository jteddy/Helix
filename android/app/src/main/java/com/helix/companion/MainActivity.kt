package com.helix.companion

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.*
import com.helix.companion.ui.screens.*
import com.helix.companion.ui.components.StatusDot
import com.helix.companion.ui.theme.*
import com.helix.companion.viewmodel.HelixViewModel

sealed class Screen(val route: String, val label: String, val icon: ImageVector) {
    object Home : Screen("home", "Home", Icons.Default.Home)
    object Recoil : Screen("recoil", "Recoil", Icons.Default.TrackChanges)
    object Flashlight : Screen("flashlight", "Flashlight", Icons.Default.FlashlightOn)
    object Settings : Screen("settings", "Settings", Icons.Default.Settings)
}

private val bottomNavItems = listOf(Screen.Home, Screen.Recoil, Screen.Flashlight, Screen.Settings)

class MainActivity : ComponentActivity() {

    private val viewModel: HelixViewModel by viewModels()

    private val notificationPermission = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { /* granted or denied — foreground service runs either way */ }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Request notification permission on Android 13+
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED) {
                notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
        }

        setContent {
            HelixTheme {
                val state by viewModel.uiState.collectAsState()

                // Show setup screen if no host configured yet
                if (state.serverHost.isBlank()) {
                    SetupScreen(onHostSet = { viewModel.setHost(it) })
                } else {
                    MainApp(state = state, viewModel = viewModel)
                }
            }
        }
    }
}

@Composable
private fun SetupScreen(onHostSet: (String) -> Unit) {
    var input by remember { mutableStateOf("") }
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(HelixBackground),
        contentAlignment = Alignment.Center
    ) {
        Column(
            modifier = Modifier.padding(32.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text("HELI", color = HelixOnSurface, fontWeight = FontWeight.Bold, fontSize = 32.sp)
            Text("X", color = HelixBlue, fontWeight = FontWeight.ExtraBold, fontSize = 32.sp)
            Spacer(Modifier.height(8.dp))
            Text("Enter your server address to connect.", color = HelixOnSurfaceDim, fontSize = 14.sp)
            Spacer(Modifier.height(24.dp))
            OutlinedTextField(
                value = input,
                onValueChange = { input = it },
                label = { Text("e.g. 192.168.1.10:8000") },
                singleLine = true,
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = HelixBlue,
                    unfocusedBorderColor = HelixSurfaceVariant,
                    focusedTextColor = HelixOnSurface,
                    unfocusedTextColor = HelixOnSurface,
                    cursorColor = HelixBlue
                ),
                modifier = Modifier.fillMaxWidth()
            )
            Spacer(Modifier.height(16.dp))
            Button(
                onClick = { if (input.isNotBlank()) onHostSet(input.trim()) },
                colors = ButtonDefaults.buttonColors(containerColor = HelixBlue),
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("Connect", color = HelixBackground, fontWeight = FontWeight.Bold)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun MainApp(state: com.helix.companion.model.HelixUiState, viewModel: HelixViewModel) {
    val navController = rememberNavController()

    Scaffold(
        containerColor = HelixBackground,
        topBar = { HelixTopBar(state) },
        bottomBar = {
            NavigationBar(containerColor = HelixSurface, tonalElevation = 0.dp) {
                val navBackStackEntry by navController.currentBackStackEntryAsState()
                val currentDestination = navBackStackEntry?.destination
                bottomNavItems.forEach { screen ->
                    val selected = currentDestination?.hierarchy?.any { it.route == screen.route } == true
                    NavigationBarItem(
                        selected = selected,
                        onClick = {
                            navController.navigate(screen.route) {
                                popUpTo(navController.graph.findStartDestination().id) { saveState = true }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        icon = {
                            Icon(screen.icon, contentDescription = screen.label,
                                tint = if (selected) HelixBlue else HelixOnSurfaceDim)
                        },
                        label = {
                            Text(screen.label, color = if (selected) HelixBlue else HelixOnSurfaceDim,
                                fontSize = 11.sp)
                        },
                        colors = NavigationBarItemDefaults.colors(
                            indicatorColor = HelixBlueDim
                        )
                    )
                }
            }
        }
    ) { padding ->
        NavHost(
            navController = navController,
            startDestination = Screen.Home.route,
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .background(HelixBackground)
        ) {
            composable(Screen.Home.route) {
                HomeScreen(
                    state = state,
                    onToggleRecoil = { viewModel.toggleRecoil() },
                    onToggleFlashlight = { viewModel.toggleFlashlight() },
                    onScriptSelected = { name, game -> viewModel.loadScript(name, game) }
                )
            }
            composable(Screen.Recoil.route) {
                RecoilScreen(
                    state = state,
                    onToggleKeybind = { viewModel.updateToggleKeybind(it) },
                    onCycleKeybind = { viewModel.updateCycleKeybind(it) },
                    onRequireAim = { viewModel.updateRequireAim(it) },
                    onLoop = { viewModel.updateLoop(it) },
                    onRandomise = { viewModel.updateRandomise(it) },
                    onReturnCrosshair = { viewModel.updateReturnCrosshair(it) },
                    onRecoilScalar = { viewModel.updateRecoilScalar(it) },
                    onXControl = { viewModel.updateXControl(it) },
                    onYControl = { viewModel.updateYControl(it) },
                    onRandomisationStrength = { viewModel.updateRandomisationStrength(it) },
                    onReturnSpeed = { viewModel.updateReturnSpeed(it) }
                )
            }
            composable(Screen.Flashlight.route) {
                FlashlightScreen(
                    state = state,
                    onKeybind = { viewModel.updateFlashlightKeybind(it) },
                    onHoldThreshold = { viewModel.updateHoldThreshold(it) },
                    onCooldown = { viewModel.updateCooldown(it) },
                    onPreFireMin = { viewModel.updatePreFireMin(it) },
                    onPreFireMax = { viewModel.updatePreFireMax(it) }
                )
            }
            composable(Screen.Settings.route) {
                SettingsScreen(
                    state = state,
                    onGameChanged = { viewModel.updateGame(it) },
                    onSensitivityChanged = { viewModel.updateSensitivity(it) },
                    onHostChanged = { viewModel.setHost(it) }
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun HelixTopBar(state: com.helix.companion.model.HelixUiState) {
    TopAppBar(
        colors = TopAppBarDefaults.topAppBarColors(containerColor = HelixSurface),
        title = {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("HELI", color = HelixOnSurface, fontWeight = FontWeight.Bold, fontSize = 20.sp)
                Text("X", color = HelixBlue, fontWeight = FontWeight.ExtraBold, fontSize = 20.sp)
                if (state.loadedScript.isNotBlank()) {
                    Text(
                        "  ·  ${state.loadedScript}",
                        color = HelixOnSurfaceDim,
                        fontSize = 13.sp,
                        modifier = Modifier.padding(start = 4.dp)
                    )
                }
            }
        },
        actions = {
            Row(
                modifier = Modifier.padding(end = 12.dp),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                StatusDot(state.makcuConnected, "MAKCU")
                StatusDot(state.wsConnected, "WS")
            }
        }
    )
}
