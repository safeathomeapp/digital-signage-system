package com.yourcompany.signagefiretv

import android.content.Context
import android.content.SharedPreferences
import android.os.Bundle
import android.util.Log
import android.widget.ImageView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.bumptech.glide.Glide
import kotlinx.coroutines.*
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.UUID

class MainActivity : AppCompatActivity() {

    private lateinit var prefs: SharedPreferences
    private lateinit var statusText: TextView
    private lateinit var imageView: ImageView

    private var currentPlaylist: JSONArray? = null
    private var currentIndex = 0
    private var isPlaying = false

    private var retryJob: Job? = null

    // DEV: set to your server on LAN for real devices.
    // Emulator: http://10.0.2.2:5000
    private val serverBaseUrl = "http://192.168.1.143:5000"

    private val deviceId: String by lazy {
        prefs.getString(PREF_DEVICE_ID, null)
            ?: UUID.randomUUID().toString().also {
                prefs.edit().putString(PREF_DEVICE_ID, it).apply()
            }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        statusText = findViewById(R.id.statusText)
        imageView = findViewById(R.id.imageView)

        statusText.text = "Starting…"
        ensureRegistered()
    }

    private fun ensureRegistered() {
        val token = prefs.getString(PREF_DEVICE_TOKEN, null)
        Log.i(TAG, "ensureRegistered: deviceId=$deviceId tokenPresent=${token != null}")
        if (token == null) registerDevice() else connectToServer()
    }

    private fun clearDeviceToken() {
        prefs.edit().remove(PREF_DEVICE_TOKEN).apply()
    }

    private fun registerDevice() {
        statusText.text = "Registering device…"

        lifecycleScope.launch(Dispatchers.IO) {
            val endpoint = "$serverBaseUrl/api/register"
            Log.i(TAG, "POST $endpoint body={device_id=$deviceId}")

            try {
                val url = URL(endpoint)
                val conn = (url.openConnection() as HttpURLConnection).apply {
                    requestMethod = "POST"
                    setRequestProperty("Content-Type", "application/json")
                    setRequestProperty("Accept", "application/json")
                    connectTimeout = 10_000
                    readTimeout = 10_000
                    doOutput = true
                }

                val body = """{"device_id":"$deviceId"}"""
                conn.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }

                val code = conn.responseCode
                val stream = if (code in 200..299) conn.inputStream else conn.errorStream
                val responseText = stream?.bufferedReader()?.use { it.readText() } ?: ""

                conn.disconnect()

                Log.i(TAG, "registerDevice: code=$code response=$responseText")

                if (code == 200) {
                    val token = try {
                        val obj = JSONObject(responseText)
                        obj.getString("token")
                    } catch (e: Exception) {
                        Log.e(TAG, "Invalid register response: $responseText", e)
                        ""
                    }

                    if (token.isBlank()) {
                        withContext(Dispatchers.Main) {
                            statusText.text = "Registration failed (no token)"
                            scheduleRetry()
                        }
                        return@launch
                    }

                    prefs.edit().putString(PREF_DEVICE_TOKEN, token).apply()

                    withContext(Dispatchers.Main) {
                        statusText.text = "Registered"
                        connectToServer()
                    }
                } else {
                    val msg = try {
                        val obj = JSONObject(responseText)
                        obj.optString("detail").ifBlank { "Pending approval" }
                    } catch (_: Exception) {
                        "Pending approval"
                    }

                    withContext(Dispatchers.Main) {
                        statusText.text = "$msg ($code)"
                        scheduleRetry()
                    }
                }

            } catch (e: Exception) {
                Log.e(TAG, "registerDevice failed", e)
                withContext(Dispatchers.Main) {
                    statusText.text = "Registration failed: ${e.javaClass.simpleName}"
                    scheduleRetry()
                }
            }
        }
    }

    private fun connectToServer() {
        lifecycleScope.launch(Dispatchers.IO) {
            val token = prefs.getString(PREF_DEVICE_TOKEN, null) ?: return@launch
            val endpoint = "$serverBaseUrl/api/playlist/$deviceId"

            Log.i(
                TAG,
                "GET $endpoint headers={X-Device-Id=$deviceId, X-Device-Token=${token.take(6)}…}"
            )

            try {
                val url = URL(endpoint)
                val conn = (url.openConnection() as HttpURLConnection).apply {
                    requestMethod = "GET"
                    setRequestProperty("X-Device-Id", deviceId)
                    setRequestProperty("X-Device-Token", token)
                    setRequestProperty("Accept", "application/json")
                    connectTimeout = 10_000
                    readTimeout = 10_000
                }

                val code = conn.responseCode
                val stream = if (code in 200..299) conn.inputStream else conn.errorStream
                val responseText = stream?.bufferedReader()?.use { it.readText() }

                conn.disconnect()

                Log.i(TAG, "connectToServer: code=$code response=${responseText?.take(400)}")

                withContext(Dispatchers.Main) {
                    if (code == 200 && !responseText.isNullOrBlank()) {
                        currentPlaylist = JSONArray(responseText)
                        startPlayback()
                    } else {
                        // If token invalid/expired or device not approved, force re-register flow
                        clearDeviceToken()
                        statusText.text = "Re-auth required ($code)"
                        ensureRegistered()
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "connectToServer failed", e)
                withContext(Dispatchers.Main) {
                    statusText.text = "Offline – retrying"
                    scheduleRetry()
                }
            }
        }
    }

    private fun startPlayback() {
        val playlist = currentPlaylist ?: return
        if (playlist.length() == 0) {
            statusText.text = "No content"
            return
        }

        isPlaying = true
        currentIndex = 0
        statusText.text = "Playing"
        displayItem(playlist.getJSONObject(0))
    }

    private fun displayItem(item: JSONObject) {
        val url = item.optString("url")
        if (url.isBlank()) return
        Glide.with(this).load(url).into(imageView)
    }

    private fun scheduleRetry() {
        retryJob?.cancel()
        retryJob = lifecycleScope.launch {
            delay(30_000)
            ensureRegistered()
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        retryJob?.cancel()
    }

    companion object {
        private const val TAG = "Signage"
        private const val PREFS_NAME = "signage_prefs"
        private const val PREF_DEVICE_ID = "device_id"
        private const val PREF_DEVICE_TOKEN = "device_token"
    }
}
