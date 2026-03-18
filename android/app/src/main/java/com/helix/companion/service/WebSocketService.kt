package com.helix.companion.service

import android.app.*
import android.content.Intent
import android.os.Binder
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.google.gson.Gson
import com.helix.companion.MainActivity
import com.helix.companion.R
import com.helix.companion.model.WsStatus
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import okhttp3.*
import java.util.concurrent.TimeUnit

class WebSocketService : Service() {

    companion object {
        const val CHANNEL_ID = "helix_ws"
        const val NOTIFICATION_ID = 1
        const val ACTION_SET_HOST = "com.helix.companion.SET_HOST"
        const val EXTRA_HOST = "host"

        // Shared flow that ViewModel observes
        val statusFlow = MutableSharedFlow<WsStatus>(replay = 1, extraBufferCapacity = 32)
        val connectedFlow = MutableSharedFlow<Boolean>(replay = 1, extraBufferCapacity = 4)
    }

    inner class LocalBinder : Binder() {
        fun getService(): WebSocketService = this@WebSocketService
    }

    private val binder = LocalBinder()
    private val gson = Gson()
    private var client: OkHttpClient? = null
    private var webSocket: WebSocket? = null
    private var currentHost: String = ""
    private var reconnectHandler = android.os.Handler(android.os.Looper.getMainLooper())
    private var reconnectRunnable: Runnable? = null
    private var intentionallyClosed = false

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, buildNotification())
        client = OkHttpClient.Builder()
            .pingInterval(10, TimeUnit.SECONDS)
            .readTimeout(0, TimeUnit.MILLISECONDS) // no timeout for WS
            .build()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_SET_HOST) {
            val host = intent.getStringExtra(EXTRA_HOST) ?: return START_STICKY
            if (host != currentHost) {
                currentHost = host
                reconnect()
            }
        }
        return START_STICKY
    }

    override fun onBind(intent: Intent): IBinder = binder

    fun setHost(host: String) {
        if (host != currentHost) {
            currentHost = host
            reconnect()
        }
    }

    private fun reconnect() {
        intentionallyClosed = false
        disconnect(intentional = false)
        connect()
    }

    private fun connect() {
        if (currentHost.isBlank()) return
        val url = "ws://$currentHost/ws"
        val request = Request.Builder().url(url).build()
        webSocket = client?.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(ws: WebSocket, response: Response) {
                connectedFlow.tryEmit(true)
            }

            override fun onMessage(ws: WebSocket, text: String) {
                runCatching {
                    val status = gson.fromJson(text, WsStatus::class.java)
                    statusFlow.tryEmit(status)
                }
            }

            override fun onFailure(ws: WebSocket, t: Throwable, response: Response?) {
                connectedFlow.tryEmit(false)
                if (!intentionallyClosed) scheduleReconnect()
            }

            override fun onClosed(ws: WebSocket, code: Int, reason: String) {
                connectedFlow.tryEmit(false)
                if (!intentionallyClosed) scheduleReconnect()
            }
        })
    }

    private fun disconnect(intentional: Boolean) {
        intentionallyClosed = intentional
        cancelReconnect()
        webSocket?.close(1000, "Reconnecting")
        webSocket = null
    }

    private fun scheduleReconnect() {
        cancelReconnect()
        reconnectRunnable = Runnable { connect() }.also {
            reconnectHandler.postDelayed(it, 3000)
        }
    }

    private fun cancelReconnect() {
        reconnectRunnable?.let { reconnectHandler.removeCallbacks(it) }
        reconnectRunnable = null
    }

    private fun createNotificationChannel() {
        val channel = NotificationChannel(
            CHANNEL_ID,
            getString(R.string.notification_channel_name),
            NotificationManager.IMPORTANCE_LOW
        ).apply { setShowBadge(false) }
        getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
    }

    private fun buildNotification(): Notification {
        val tapIntent = Intent(this, MainActivity::class.java)
        val pendingIntent = PendingIntent.getActivity(
            this, 0, tapIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(getString(R.string.notification_title))
            .setContentText(getString(R.string.notification_text))
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .setSilent(true)
            .build()
    }

    override fun onDestroy() {
        disconnect(intentional = true)
        client?.dispatcher?.executorService?.shutdown()
        super.onDestroy()
    }
}
