package com.yourcompany.signagefiretv

import android.content.Context
import android.content.SharedPreferences
import android.os.Bundle
import android.view.KeyEvent
import android.view.View
import android.widget.ImageView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.bumptech.glide.Glide
import kotlinx.coroutines.*
import org.json.JSONArray
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
    private var settingsVisible = false

    private var refreshJob: Job? = null
    private var retryJob: Job? = null

    private val serverBaseUrl = "http://10.0.2.2:5000"
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
        if (token == null) {
            registerDevice()
        } else {
            connectToServer()
        }
    }

    private fun clearDeviceToken() {
        prefs.edit().remove(PREF_DEVICE_TOKEN).apply()
    }

    private fun registerDevice() {
        statusText.text = "Registering device…"
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val url = URL("$serverBaseUrl/api/register")
                val conn = url.openConnection() as HttpURLConnection
                conn.requestMethod = "POST"
                conn.setRequestProperty("Content-Type", "application/json")
                conn.doOutput = true

                val body = """{"device_id":"$deviceId"}"""
                conn.outputStream.use { it.write(body.toByteArray()) }

                val code = conn.responseCode
                val response = conn.inputStream.bufferedReader().use { it.readText() }

                conn.disconnect()

                if (code == 200) {
                    val token = response.trim()
                    prefs.edit().putString(PREF_DEVICE_TOKEN, token).apply()
                    withContext(Dispatchers.Main) {
                        connectToServer()
                    }
                } else {
                    withContext(Dispatchers.Main) {
                        statusText.text = "Pending approval"
                        scheduleRetry()
                    }
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    statusText.text = "Registration failed"
                    scheduleRetry()
                }
            }
        }
    }

    private fun connectToServer() {
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val token = prefs.getString(PREF_DEVICE_TOKEN, null) ?: return@launch
                val url = URL("$serverBaseUrl/api/playlist/$deviceId")
                val conn = url.openConnection() as HttpURLConnection
                conn.setRequestProperty("X-Device-Id", deviceId)
                conn.setRequestProperty("X-Device-Token", token)

                val code = conn.responseCode
                val body = if (code == 200) {
                    conn.inputStream.bufferedReader().use { it.readText() }
                } else null

                conn.disconnect()

                withContext(Dispatchers.Main) {
                    if (code == 200 && body != null) {
                        currentPlaylist = JSONArray(body)
                        startPlayback()
                    } else {
                        clearDeviceToken()
                        ensureRegistered()
                    }
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    statusText.text = "Offline – retrying"
                    scheduleRetry()
                }
            }
        }
    }

    private fun startPlayback() {
        val playlist = currentPlaylist ?: return
        if (playlist.length() == 0) return

        isPlaying = true
        currentIndex = 0
        displayItem(playlist.getJSONObject(0))
    }

    private fun displayItem(item: org.json.JSONObject) {
        val url = item.optString("url")
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
        refreshJob?.cancel()
        retryJob?.cancel()
    }

    companion object {
        private const val PREFS_NAME = "signage_prefs"
        private const val PREF_DEVICE_ID = "device_id"
        private const val PREF_DEVICE_TOKEN = "device_token"
    }
}
