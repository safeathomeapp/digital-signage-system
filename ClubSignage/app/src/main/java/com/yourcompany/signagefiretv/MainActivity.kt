package com.yourcompany.signagefiretv

import android.content.Context
import android.content.SharedPreferences
import android.os.Bundle
import android.util.Log
import android.view.KeyEvent
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.ImageView
import android.widget.LinearLayout
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
    private lateinit var deviceInfoText: TextView
    private lateinit var contentInfoText: TextView
    private lateinit var imageView: ImageView
    private lateinit var imageViewAlt: ImageView
    private lateinit var settingsLayout: LinearLayout
    private lateinit var serverIpInput: EditText
    private lateinit var deviceNameInput: EditText
    private lateinit var testConnectionButton: Button
    private lateinit var saveSettingsButton: Button

    private var currentPlaylist: JSONArray? = null
    private var currentIndex = 0
    private var isPlaying = false

    private var retryJob: Job? = null
    private var playbackJob: Job? = null

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
        deviceInfoText = findViewById(R.id.deviceInfoText)
        contentInfoText = findViewById(R.id.contentInfoText)
        imageView = findViewById(R.id.imageView)
        imageViewAlt = findViewById(R.id.imageViewAlt)
        settingsLayout = findViewById(R.id.settingsLayout)
        serverIpInput = findViewById(R.id.serverIpInput)
        deviceNameInput = findViewById(R.id.deviceNameInput)
        testConnectionButton = findViewById(R.id.testConnectionButton)
        saveSettingsButton = findViewById(R.id.saveSettingsButton)

        setupSettingsUi()

        statusText.text = "Starting…"
        ensureRegistered()
    }

    private fun setupSettingsUi() {
        val savedServer = prefs.getString(PREF_SERVER_URL, "") ?: ""
        if (savedServer.isNotBlank()) {
            serverIpInput.setText(savedServer.replace("http://", "").replace("https://", ""))
        }

        val savedName = prefs.getString(PREF_DEVICE_NAME, "") ?: ""
        if (savedName.isNotBlank()) deviceNameInput.setText(savedName)

        testConnectionButton.setOnClickListener { testServerConnection() }
        saveSettingsButton.setOnClickListener { saveServerSettings() }

        updateDeviceInfo()
        updateContentInfo("Idle")

        if (savedServer.isBlank()) {
            showSettings(true)
            statusText.text = "Set server address"
        }
    }

    private fun updateDeviceInfo() {
        val server = prefs.getString(PREF_SERVER_URL, "") ?: ""
        val name = prefs.getString(PREF_DEVICE_NAME, "") ?: ""
        val nameText = if (name.isBlank()) "Unnamed" else name
        deviceInfoText.text = "Device: $nameText\nID: ${deviceId.take(8)}…\nServer: $server"
    }

    private fun updateContentInfo(info: String) {
        contentInfoText.text = "Content: $info"
    }

    private fun showSettings(show: Boolean) {
        settingsLayout.visibility = if (show) View.VISIBLE else View.GONE
        if (show) {
            serverIpInput.requestFocus()
        }
    }

    private fun testServerConnection() {
        val baseUrl = buildServerUrl(serverIpInput.text?.toString().orEmpty())
        if (baseUrl.isBlank()) {
            statusText.text = "Enter server address"
            return
        }

        statusText.text = "Testing connection…"
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val url = URL("$baseUrl/api/system/status")
                val conn = (url.openConnection() as HttpURLConnection).apply {
                    requestMethod = "GET"
                    connectTimeout = 5_000
                    readTimeout = 5_000
                }
                val code = conn.responseCode
                conn.disconnect()

                withContext(Dispatchers.Main) {
                    statusText.text = if (code == 200) "Server OK" else "Server error ($code)"
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    statusText.text = "Server not reachable"
                }
            }
        }
    }

    private fun saveServerSettings() {
        val baseUrl = buildServerUrl(serverIpInput.text?.toString().orEmpty())
        if (baseUrl.isBlank()) {
            statusText.text = "Enter server address"
            return
        }

        val deviceName = deviceNameInput.text?.toString()?.trim().orEmpty()

        prefs.edit()
            .putString(PREF_SERVER_URL, baseUrl)
            .putString(PREF_DEVICE_NAME, deviceName)
            .remove(PREF_DEVICE_TOKEN)
            .apply()

        updateDeviceInfo()
        showSettings(false)
        statusText.text = "Saved. Connecting…"
        ensureRegistered()
    }

    private fun buildServerUrl(input: String): String {
        val trimmed = input.trim().removeSuffix("/")
        if (trimmed.isBlank()) return ""
        return if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
            trimmed
        } else {
            "http://$trimmed"
        }
    }

    private fun getServerBaseUrl(): String {
        return prefs.getString(PREF_SERVER_URL, "") ?: ""
    }

    private fun ensureRegistered() {
        val serverBaseUrl = getServerBaseUrl()
        if (serverBaseUrl.isBlank()) {
            showSettings(true)
            statusText.text = "Set server address"
            return
        }

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
            val serverBaseUrl = getServerBaseUrl()
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
                        showSettings(true)
                        scheduleRetry()
                    }
                }
            }
    }

    private fun connectToServer() {
        lifecycleScope.launch(Dispatchers.IO) {
            val token = prefs.getString(PREF_DEVICE_TOKEN, null) ?: return@launch
            val serverBaseUrl = getServerBaseUrl()
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
                        currentPlaylist = try {
                            val obj = JSONObject(responseText)
                            obj.getJSONArray("playlist")
                        } catch (_: Exception) {
                            // Backward compatibility if server ever returns a raw array
                            JSONArray(responseText)
                        }
                        startPlayback()
                    } else {
                        // If token invalid/expired or device not approved, force re-register flow
                        clearDeviceToken()
                        statusText.text = "Re-auth required ($code)"
                        showSettings(true)
                        ensureRegistered()
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "connectToServer failed", e)
                withContext(Dispatchers.Main) {
                    statusText.text = "Offline – retrying"
                    showSettings(true)
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
        updateContentInfo("Playlist: ${playlist.length()} items")
        playbackJob?.cancel()
        playbackJob = lifecycleScope.launch {
            while (isActive && isPlaying) {
                val item = playlist.getJSONObject(currentIndex)
                displayItem(item)
                val delayMs = getDisplayDurationMs(item)
                delay(delayMs)
                currentIndex = (currentIndex + 1) % playlist.length()
            }
        }
    }

    private fun displayItem(item: JSONObject) {
        val url = item.optString("url")
        if (url.isBlank()) return
        val filename = item.optString("filename", "Unknown")
        val transitionType = item.optString("transition_type", "fade")
        val transitionDuration = item.optDouble("transition_duration", 1.0)
        updateContentInfo("$filename (${transitionType})")
        showImageWithTransition(url, transitionType, transitionDuration)
    }

    private fun showImageWithTransition(url: String, typeRaw: String, durationSeconds: Double) {
        val type = typeRaw.lowercase().ifBlank { "fade" }
        val durationMs = (durationSeconds.coerceIn(0.1, 5.0) * 1000).toLong()

        val incoming = if (imageView.visibility == View.VISIBLE) imageViewAlt else imageView
        val outgoing = if (incoming === imageView) imageViewAlt else imageView

        val outgoingHasImage = outgoing.drawable != null && outgoing.visibility == View.VISIBLE
        if (type == "none" || durationMs <= 0 || !outgoingHasImage) {
            incoming.alpha = 1f
            incoming.translationX = 0f
            incoming.translationY = 0f
            incoming.scaleX = 1f
            incoming.scaleY = 1f
            incoming.visibility = View.VISIBLE
            Glide.with(this).load(url).into(incoming)
            outgoing.visibility = View.GONE
            return
        }

        val width = (incoming.width.takeIf { it > 0 } ?: resources.displayMetrics.widthPixels).toFloat()
        val height = (incoming.height.takeIf { it > 0 } ?: resources.displayMetrics.heightPixels).toFloat()

        // Prepare incoming start state
        incoming.alpha = 0f
        incoming.translationX = 0f
        incoming.translationY = 0f
        incoming.scaleX = 1f
        incoming.scaleY = 1f

        when (type) {
            "slide-left" -> incoming.translationX = width
            "slide-right" -> incoming.translationX = -width
            "slide-up" -> incoming.translationY = height
            "slide-down" -> incoming.translationY = -height
            "zoom-in" -> {
                incoming.scaleX = 1.2f
                incoming.scaleY = 1.2f
            }
            "zoom-out" -> {
                incoming.scaleX = 0.8f
                incoming.scaleY = 0.8f
            }
        }

        incoming.visibility = View.VISIBLE
        Glide.with(this).load(url).into(incoming)

        // Animate outgoing out (fade + optional slide)
        when (type) {
            "slide-left" -> outgoing.animate().translationX(-width).alpha(0f).setDuration(durationMs)
            "slide-right" -> outgoing.animate().translationX(width).alpha(0f).setDuration(durationMs)
            "slide-up" -> outgoing.animate().translationY(-height).alpha(0f).setDuration(durationMs)
            "slide-down" -> outgoing.animate().translationY(height).alpha(0f).setDuration(durationMs)
            else -> outgoing.animate().alpha(0f).setDuration(durationMs)
        }.start()

        // Animate incoming in
        incoming.animate()
            .alpha(1f)
            .translationX(0f)
            .translationY(0f)
            .scaleX(1f)
            .scaleY(1f)
            .setDuration(durationMs)
            .withEndAction {
                outgoing.visibility = View.GONE
                outgoing.alpha = 1f
                outgoing.translationX = 0f
                outgoing.translationY = 0f
                outgoing.scaleX = 1f
                outgoing.scaleY = 1f
            }
            .start()
    }

    private fun getDisplayDurationMs(item: JSONObject): Long {
        val seconds = try {
            item.optInt("display_duration", 10)
        } catch (_: Exception) {
            10
        }
        return (seconds.coerceAtLeast(3) * 1000).toLong()
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
        playbackJob?.cancel()
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        if (keyCode == KeyEvent.KEYCODE_DPAD_CENTER || keyCode == KeyEvent.KEYCODE_MENU) {
            val isVisible = settingsLayout.visibility == View.VISIBLE
            showSettings(!isVisible)
            return true
        }
        if (keyCode == KeyEvent.KEYCODE_BACK && settingsLayout.visibility == View.VISIBLE) {
            showSettings(false)
            return true
        }
        return super.onKeyDown(keyCode, event)
    }

    companion object {
        private const val TAG = "Signage"
        private const val PREFS_NAME = "signage_prefs"
        private const val PREF_DEVICE_ID = "device_id"
        private const val PREF_DEVICE_TOKEN = "device_token"
        private const val PREF_SERVER_URL = "server_url"
        private const val PREF_DEVICE_NAME = "device_name"
    }
}
