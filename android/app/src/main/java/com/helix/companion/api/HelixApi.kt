package com.helix.companion.api

import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import com.helix.companion.model.*
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.IOException
import java.util.concurrent.TimeUnit

class HelixApi(private val host: String) {

    private val gson = Gson()
    private val json = "application/json; charset=utf-8".toMediaType()

    private val client = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(5, TimeUnit.SECONDS)
        .writeTimeout(5, TimeUnit.SECONDS)
        .build()

    private fun baseUrl() = "http://$host"

    // --- Generic helpers ---

    private fun get(path: String): Response {
        val request = Request.Builder().url("${baseUrl()}$path").get().build()
        return client.newCall(request).execute()
    }

    private fun post(path: String, body: Any): Response {
        val reqBody = gson.toJson(body).toRequestBody(json)
        val request = Request.Builder().url("${baseUrl()}$path").post(reqBody).build()
        return client.newCall(request).execute()
    }

    private fun delete(path: String): Response {
        val request = Request.Builder().url("${baseUrl()}$path").delete().build()
        return client.newCall(request).execute()
    }

    private inline fun <reified T> Response.parse(): T {
        val body = this.body?.string() ?: throw IOException("Empty response")
        return gson.fromJson(body, object : TypeToken<T>() {}.type)
    }

    // --- API calls (run on IO dispatcher in ViewModel) ---

    fun getFullState(): FullState = get("/api/state").parse()

    fun toggleRecoil(): Unit { post("/api/recoil/toggle", emptyMap<String, Any>()).close() }

    fun toggleFlashlight(): Unit { post("/api/flashlight/toggle", emptyMap<String, Any>()).close() }

    fun updateRecoil(body: RecoilUpdateBody): Unit { post("/api/recoil", body).close() }

    fun updateFlashlight(body: FlashlightUpdateBody): Unit { post("/api/flashlight", body).close() }

    fun updateSettings(body: SettingsUpdateBody): Unit { post("/api/settings", body).close() }

    fun getScripts(game: String? = null): List<String> {
        val path = if (game != null) "/api/scripts?game=$game" else "/api/scripts"
        val resp = get(path).parse<Map<String, List<String>>>()
        return resp["scripts"] ?: emptyList()
    }

    fun getGames(): List<String> {
        val resp = get("/api/scripts/games").parse<Map<String, List<String>>>()
        return resp["games"] ?: emptyList()
    }

    fun loadScript(name: String, game: String? = null): Unit {
        val path = if (game != null) "/api/scripts/load/$game/$name"
                   else "/api/scripts/load/$name"
        post(path, emptyMap<String, Any>()).close()
    }

    // Build WebSocket URL
    fun wsUrl() = "ws://$host/ws"
}
