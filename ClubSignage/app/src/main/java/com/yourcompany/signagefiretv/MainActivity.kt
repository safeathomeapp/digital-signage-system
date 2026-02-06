package com.yourcompany.signagefiretv

import android.content.Context
import android.content.SharedPreferences
import android.net.Uri
import android.os.Bundle
import android.view.KeyEvent
import android.view.View
import android.view.WindowManager
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.constraintlayout.widget.ConstraintLayout
import androidx.lifecycle.lifecycleScope
import com.bumptech.glide.Glide
import com.google.android.exoplayer2.ExoPlayer
import com.google.android.exoplayer2.MediaItem
import com.google.android.exoplayer2.Player
import com.google.android.exoplayer2.source.MediaSource
import com.google.android.exoplayer2.source.ProgressiveMediaSource
import com.google.android.exoplayer2.upstream.DefaultDataSource
import kotlinx.coroutines.*
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.NetworkInterface
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.random.Random

class MainActivity : AppCompatActivity() {

    // UI Components
    private lateinit var mainContainer: ConstraintLayout
    private lateinit var imageView: ImageView
    private lateinit var videoView: com.google.android.exoplayer2.ui.PlayerView
    private lateinit var statusText: TextView
    private lateinit var deviceInfoText: TextView
    private lateinit var contentInfoText: TextView
    private lateinit var settingsLayout: LinearLayout
    private lateinit var serverIpInput: EditText
    private lateinit var deviceNameInput: EditText
    private lateinit var saveSettingsButton: Button
    private lateinit var testConnectionButton: Button

    // ExoPlayer for video playback
    private var exoPlayer: ExoPlayer? = null

    // Content management
    private var displayJob: Job? = null
    private var connectJob: Job? = null
    private var retryJob: Job? = null
    private var refreshJob: Job? = null

    private var currentIndex = 0
    private var currentPlaylist: JSONArray? = null
    private var isPlaying = false
    private var settingsVisible = false

    // Device info
    private var deviceId: String = ""
    private var serverIp: String = "192.168.1.143:5000"

    // Cache keys
    private val PREF_PLAYLIST_JSON = "cached_playlist_json"
    private val PREF_PLAYLIST_SAVED_AT = "cached_playlist_saved_at"

    // Runtime flags
    private var usingCache = false
    private var lastSyncEpochMs: Long = 0L

    private val prefs: SharedPreferences by lazy {
        getSharedPreferences("signage_prefs", Context.MODE_PRIVATE)
    }

    // Auto-refresh
    private val refreshIntervalMs = 30_000L // 30 seconds

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        setupFullScreen()
        setContentView(R.layout.activity_main)

        initViews()
        loadSettings()
        generateDeviceId()

        // Phase 2: start playback from cached playlist immediately if available
        tryStartFromCache()

        // Always attempt live fetch afterwards
        connectToServer(reason = "startup")
    }


    private fun setupFullScreen() {
        window.decorView.systemUiVisibility = (
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                or View.SYSTEM_UI_FLAG_FULLSCREEN
                or View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                or View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                or View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                or View.SYSTEM_UI_FLAG_LAYOUT_STABLE
            )

        // Keep screen on
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
    }

    private fun initViews() {
        mainContainer = findViewById(R.id.mainContainer)
        imageView = findViewById(R.id.imageView)
        videoView = findViewById(R.id.videoView)
        statusText = findViewById(R.id.statusText)
        deviceInfoText = findViewById(R.id.deviceInfoText)
        contentInfoText = findViewById(R.id.contentInfoText)
        settingsLayout = findViewById(R.id.settingsLayout)
        serverIpInput = findViewById(R.id.serverIpInput)
        deviceNameInput = findViewById(R.id.deviceNameInput)
        saveSettingsButton = findViewById(R.id.saveSettingsButton)
        testConnectionButton = findViewById(R.id.testConnectionButton)

        initializePlayer()

        saveSettingsButton.setOnClickListener { saveSettings() }
        testConnectionButton.setOnClickListener { testConnection() }

        settingsLayout.visibility = View.GONE
    }

    private fun initializePlayer() {
        exoPlayer = ExoPlayer.Builder(this).build()
        videoView.player = exoPlayer
        videoView.useController = false

        exoPlayer?.addListener(object : Player.Listener {
            override fun onPlaybackStateChanged(playbackState: Int) {
                if (playbackState == Player.STATE_ENDED) {
                    lifecycleScope.launch { moveToNextContent() }
                }
            }
        })
    }

    private fun loadSettings() {
        serverIp = prefs.getString("server_ip", "192.168.1.143:5000") ?: "192.168.1.143:5000"
        val deviceName = prefs.getString("device_name", "") ?: ""

        serverIpInput.setText(serverIp)
        deviceNameInput.setText(deviceName)
    }

    private fun saveSettings() {
        serverIp = serverIpInput.text.toString().trim()
        val deviceName = deviceNameInput.text.toString().trim()

        prefs.edit()
            .putString("server_ip", serverIp)
            .putString("device_name", deviceName)
            .apply()

        hideSettings()
        connectToServer(reason = "settings_saved")

        Toast.makeText(this, "Settings saved", Toast.LENGTH_SHORT).show()
    }

    private fun testConnection() {
        val testIp = serverIpInput.text.toString().trim()
        lifecycleScope.launch(Dispatchers.IO) {
            val result = runCatching {
                val url = URL("http://$testIp/api/system/status")
                val connection = (url.openConnection() as HttpURLConnection).apply {
                    requestMethod = "GET"
                    connectTimeout = 5_000
                    readTimeout = 5_000
                }
                val code = connection.responseCode
                connection.disconnect()
                code
            }

            withContext(Dispatchers.Main) {
                result.onSuccess { code ->
                    if (code == 200) {
                        Toast.makeText(this@MainActivity, "Connection successful!", Toast.LENGTH_SHORT).show()
                    } else {
                        Toast.makeText(this@MainActivity, "Server error: $code", Toast.LENGTH_SHORT).show()
                    }
                }.onFailure { e ->
                    Toast.makeText(this@MainActivity, "Connection failed: ${e.message}", Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    private fun generateDeviceId() {
        deviceId = prefs.getString("device_id", "") ?: ""

        if (deviceId.isEmpty()) {
            deviceId = try {
                val interfaces = NetworkInterface.getNetworkInterfaces()
                var mac = ""

                for (networkInterface in interfaces) {
                    if (networkInterface.name.equals("wlan0", true)) {
                        val macBytes = networkInterface.hardwareAddress
                        if (macBytes != null) {
                            mac = macBytes.joinToString(":") { "%02x".format(it) }
                            break
                        }
                    }
                }

                if (mac.isNotEmpty()) {
                    "firetv-${mac.replace(":", "").takeLast(8)}"
                } else {
                    "firetv-${Random.nextInt(100000, 999999)}"
                }
            } catch (_: Exception) {
                "firetv-${Random.nextInt(100000, 999999)}"
            }

            prefs.edit().putString("device_id", deviceId).apply()
        }

        updateDeviceInfo()
    }

    private fun updateDeviceInfo() {
        val currentTime = SimpleDateFormat("HH:mm:ss", Locale.getDefault()).format(Date())
        val mode = if (usingCache) "CACHED" else "LIVE"
        val lastSync = formatLastSync()
        deviceInfoText.text = "Device: $deviceId | Server: $serverIp | Mode: $mode | Last sync: $lastSync | Time: $currentTime"
    }


    private fun connectToServer(reason: String) {
        statusText.text = "Connecting to server..."

        // Ensure only ONE in-flight request at a time.
        connectJob?.cancel()

        connectJob = lifecycleScope.launch(Dispatchers.IO) {
            val result = runCatching {
                val url = URL("http://$serverIp/api/playlist/$deviceId")
                val connection = (url.openConnection() as HttpURLConnection).apply {
                    requestMethod = "GET"
                    connectTimeout = 10_000
                    readTimeout = 15_000
                }

                val responseCode = connection.responseCode
                val body = if (responseCode == 200) {
                    connection.inputStream.bufferedReader().use { it.readText() }
                } else {
                    connection.errorStream?.bufferedReader()?.use { it.readText() }
                }

                connection.disconnect()
                responseCode to body
            }

            withContext(Dispatchers.Main) {
                result.onSuccess { (code, body) ->
                    if (code == 200 && body != null) {
                        usingCache = false
						try {
							parseAndDisplayPlaylist(body)
							savePlaylistCache(body) // only after successful parse
							statusText.text = "Live mode: playlist loaded"
						} catch (e: Exception) {
							statusText.text = "Live playlist parse failed: ${e.message}"
							if (!isPlaying) {
								tryStartFromCache()
							}
							scheduleRetry(reason = "live_parse_failed")
						}

                    } else {
                        statusText.text = "Server error: $code"
                        if (!isPlaying) {
                            tryStartFromCache()
                        }
                        scheduleRetry(reason = "server_error_$code")
                    }
                }.onFailure { e ->
                    statusText.text = "Connection failed: ${e.message}"
                    if (!isPlaying) {
                        tryStartFromCache()
                    }
                    scheduleRetry(reason = "exception")
                }
            }
        }
    }

    private fun savePlaylistCache(rawJson: String) {
        val now = System.currentTimeMillis()
        prefs.edit()
            .putString(PREF_PLAYLIST_JSON, rawJson)
            .putLong(PREF_PLAYLIST_SAVED_AT, now)
            .apply()
        lastSyncEpochMs = now
    }

    private fun loadPlaylistCache(): String? {
        val cached = prefs.getString(PREF_PLAYLIST_JSON, null)
        lastSyncEpochMs = prefs.getLong(PREF_PLAYLIST_SAVED_AT, 0L)
        return cached
    }

    private fun tryStartFromCache(): Boolean {
        val cachedJson = loadPlaylistCache() ?: return false
        return try {
            usingCache = true
            statusText.text = "Offline mode: using cached playlist"
            parseAndDisplayPlaylist(cachedJson) // reuse your existing parser
            true
        } catch (_: Exception) {
            false
        }
    }

    private fun formatLastSync(): String {
        if (lastSyncEpochMs <= 0L) return "never"
        val sdf = java.text.SimpleDateFormat("yyyy-MM-dd HH:mm:ss", java.util.Locale.getDefault())
        return sdf.format(java.util.Date(lastSyncEpochMs))
    }

    private fun scheduleRetry(reason: String) {
        // Ensure only ONE retry timer exists.
        retryJob?.cancel()
        retryJob = lifecycleScope.launch {
            delay(30_000)
            if (!settingsVisible) {
                connectToServer(reason = "retry_$reason")
            }
        }
    }

    private fun parseAndDisplayPlaylist(jsonResponse: String) {
        try {
            val json = JSONObject(jsonResponse)
            val playlistArray = json.getJSONArray("playlist")
            currentPlaylist = playlistArray

            if (playlistArray.length() == 0) {
                statusText.text = "No content assigned - Connect via web interface"
                contentInfoText.text = "Server: http://$serverIp"
                stopPlayback()
                return
            }

            statusText.text = "Content loaded: ${playlistArray.length()} items"

            currentIndex = 0
            startContentPlayback()

        } catch (e: Exception) {
            statusText.text = "Error parsing playlist: ${e.message}"
            scheduleRetry(reason = "parse")
        }
    }

    private fun startContentPlayback() {
        val playlist = currentPlaylist
        if (playlist == null || playlist.length() == 0) return

        stopPlayback()
        isPlaying = true

        displayJob = lifecycleScope.launch {
            while (isActive && isPlaying) {
                val currentItem = playlist.getJSONObject(currentIndex)

                displayContent(currentItem)

                if (currentItem.optString("file_type") == "image") {
                    val duration = currentItem.optInt("display_duration", 10).coerceAtLeast(1)
                    delay(duration * 1000L)

                    if (!isActive || !isPlaying) break

                    if (playlist.length() > 1) {
                        val nextIndex = (currentIndex + 1) % playlist.length()
                        val nextItem = playlist.getJSONObject(nextIndex)
                        applyTransition(nextItem)
                        currentIndex = nextIndex
                    }
                } else {
                    // For videos, the ExoPlayer listener moves to next item.
                    delay(1000)
                }
            }
        }
    }

    private fun displayContent(contentItem: JSONObject) {
        val filename = contentItem.optString("filename", "unknown")
        val fileType = contentItem.optString("file_type", "image")
        val duration = contentItem.optInt("display_duration", 10)
        val url = contentItem.optString("url", "")

        contentInfoText.text = """
            Playing: $filename (${currentIndex + 1}/${currentPlaylist?.length() ?: 1})
            Type: $fileType | Duration: ${duration}s
        """.trimIndent()

        if (fileType == "image") {
            imageView.visibility = View.VISIBLE
            videoView.visibility = View.GONE

            if (url.isBlank()) {
                statusText.text = "Missing image URL for $filename"
            } else {
                Glide.with(this).load(url).into(imageView)
            }
        } else {
            imageView.visibility = View.GONE
            videoView.visibility = View.VISIBLE

            if (url.isBlank()) {
                statusText.text = "Missing video URL for $filename"
                lifecycleScope.launch {
                    delay(1500)
                    moveToNextContent()
                }
            } else {
                playVideo(url)
            }
        }

        updateDeviceInfo()
    }

    private fun playVideo(url: String) {
        try {
            val uri = Uri.parse(url)
            val dataSourceFactory = DefaultDataSource.Factory(this)
            val mediaSource: MediaSource = ProgressiveMediaSource.Factory(dataSourceFactory)
                .createMediaSource(MediaItem.fromUri(uri))

            exoPlayer?.apply {
                stop()
                clearMediaItems()
                setMediaSource(mediaSource)
                prepare()
                playWhenReady = true
            }

        } catch (e: Exception) {
            statusText.text = "Video playback error: ${e.message}"
            lifecycleScope.launch {
                delay(2000)
                moveToNextContent()
            }
        }
    }

    private fun moveToNextContent() {
        val playlist = currentPlaylist
        if (playlist != null && playlist.length() > 1) {
            currentIndex = (currentIndex + 1) % playlist.length()
            val nextItem = playlist.getJSONObject(currentIndex)
            displayContent(nextItem)
        }
    }

    private suspend fun applyTransition(nextItem: JSONObject) {
        val transitionType = nextItem.optString("transition_type", "fade")
        val transitionDuration = nextItem.optDouble("transition_duration", 1.0)

        when (transitionType) {
            "fade" -> {
                imageView.animate()
                    .alpha(0f)
                    .setDuration((transitionDuration * 500).toLong())
                    .start()

                delay((transitionDuration * 500).toLong())

                if (nextItem.optString("file_type") == "image") {
                    Glide.with(this@MainActivity)
                        .load(nextItem.optString("url"))
                        .into(imageView)
                }

                imageView.animate()
                    .alpha(1f)
                    .setDuration((transitionDuration * 500).toLong())
                    .start()
            }

            "slide-left" -> {
                imageView.animate()
                    .translationX(-imageView.width.toFloat())
                    .setDuration((transitionDuration * 1000).toLong())
                    .start()

                delay((transitionDuration * 1000).toLong())

                if (nextItem.optString("file_type") == "image") {
                    Glide.with(this@MainActivity)
                        .load(nextItem.optString("url"))
                        .into(imageView)
                }

                imageView.translationX = imageView.width.toFloat()
                imageView.animate()
                    .translationX(0f)
                    .setDuration((transitionDuration * 1000).toLong())
                    .start()
            }

            "slide-right" -> {
                imageView.animate()
                    .translationX(imageView.width.toFloat())
                    .setDuration((transitionDuration * 1000).toLong())
                    .start()

                delay((transitionDuration * 1000).toLong())

                if (nextItem.optString("file_type") == "image") {
                    Glide.with(this@MainActivity)
                        .load(nextItem.optString("url"))
                        .into(imageView)
                }

                imageView.translationX = -imageView.width.toFloat()
                imageView.animate()
                    .translationX(0f)
                    .setDuration((transitionDuration * 1000).toLong())
                    .start()
            }

            "slide-up" -> {
                imageView.animate()
                    .translationY(-imageView.height.toFloat())
                    .setDuration((transitionDuration * 1000).toLong())
                    .start()

                delay((transitionDuration * 1000).toLong())

                if (nextItem.optString("file_type") == "image") {
                    Glide.with(this@MainActivity)
                        .load(nextItem.optString("url"))
                        .into(imageView)
                }

                imageView.translationY = imageView.height.toFloat()
                imageView.animate()
                    .translationY(0f)
                    .setDuration((transitionDuration * 1000).toLong())
                    .start()
            }

            "slide-down" -> {
                imageView.animate()
                    .translationY(imageView.height.toFloat())
                    .setDuration((transitionDuration * 1000).toLong())
                    .start()

                delay((transitionDuration * 1000).toLong())

                if (nextItem.optString("file_type") == "image") {
                    Glide.with(this@MainActivity)
                        .load(nextItem.optString("url"))
                        .into(imageView)
                }

                imageView.translationY = -imageView.height.toFloat()
                imageView.animate()
                    .translationY(0f)
                    .setDuration((transitionDuration * 1000).toLong())
                    .start()
            }

            "zoom-in" -> {
                imageView.animate()
                    .scaleX(0.3f)
                    .scaleY(0.3f)
                    .alpha(0f)
                    .setDuration((transitionDuration * 1000).toLong())
                    .start()

                delay((transitionDuration * 1000).toLong())

                if (nextItem.optString("file_type") == "image") {
                    Glide.with(this@MainActivity)
                        .load(nextItem.optString("url"))
                        .into(imageView)
                }

                imageView.scaleX = 1.5f
                imageView.scaleY = 1.5f
                imageView.alpha = 0f
                imageView.animate()
                    .scaleX(1f)
                    .scaleY(1f)
                    .alpha(1f)
                    .setDuration((transitionDuration * 1000).toLong())
                    .start()
            }

            "zoom-out" -> {
                imageView.animate()
                    .scaleX(1.5f)
                    .scaleY(1.5f)
                    .alpha(0f)
                    .setDuration((transitionDuration * 1000).toLong())
                    .start()

                delay((transitionDuration * 1000).toLong())

                if (nextItem.optString("file_type") == "image") {
                    Glide.with(this@MainActivity)
                        .load(nextItem.optString("url"))
                        .into(imageView)
                }

                imageView.scaleX = 0.3f
                imageView.scaleY = 0.3f
                imageView.alpha = 0f
                imageView.animate()
                    .scaleX(1f)
                    .scaleY(1f)
                    .alpha(1f)
                    .setDuration((transitionDuration * 1000).toLong())
                    .start()
            }

            else -> {
                if (nextItem.optString("file_type") == "image") {
                    Glide.with(this@MainActivity)
                        .load(nextItem.optString("url"))
                        .into(imageView)
                }
            }
        }
    }

    private fun stopPlayback() {
        isPlaying = false
        displayJob?.cancel()
        displayJob = null
        exoPlayer?.stop()
    }

    private fun showSettings() {
        settingsVisible = true
        settingsLayout.visibility = View.VISIBLE
        stopPlayback()
    }

    private fun hideSettings() {
        settingsVisible = false
        settingsLayout.visibility = View.GONE
        if (currentPlaylist != null && currentPlaylist!!.length() > 0) {
            startContentPlayback()
        }
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        return when (keyCode) {
            KeyEvent.KEYCODE_MENU,
            KeyEvent.KEYCODE_DPAD_CENTER -> {
                if (settingsVisible) hideSettings() else showSettings()
                true
            }

            KeyEvent.KEYCODE_BACK -> {
                if (settingsVisible) {
                    hideSettings()
                    true
                } else {
                    super.onKeyDown(keyCode, event)
                }
            }

            KeyEvent.KEYCODE_DPAD_LEFT -> {
                val playlist = currentPlaylist
                if (!settingsVisible && playlist != null && playlist.length() > 1) {
                    currentIndex = if (currentIndex > 0) currentIndex - 1 else playlist.length() - 1
                    displayContent(playlist.getJSONObject(currentIndex))
                }
                true
            }

            KeyEvent.KEYCODE_DPAD_RIGHT -> {
                val playlist = currentPlaylist
                if (!settingsVisible && playlist != null && playlist.length() > 1) {
                    currentIndex = (currentIndex + 1) % playlist.length()
                    displayContent(playlist.getJSONObject(currentIndex))
                }
                true
            }

            else -> super.onKeyDown(keyCode, event)
        }
    }

    override fun onStart() {
        super.onStart()
        setupFullScreen()

        // Ensure only ONE refresh loop exists.
        refreshJob?.cancel()
        refreshJob = lifecycleScope.launch {
            while (isActive) {
                delay(refreshIntervalMs)
                if (!settingsVisible && isPlaying) {
                    connectToServer(reason = "auto_refresh")
                }
            }
        }

        if (!settingsVisible && currentPlaylist != null && currentPlaylist!!.length() > 0) {
            startContentPlayback()
        }
    }

    override fun onStop() {
        super.onStop()
        stopPlayback()
        refreshJob?.cancel()
        refreshJob = null
        retryJob?.cancel()
        retryJob = null
        connectJob?.cancel()
        connectJob = null
    }

    override fun onDestroy() {
        super.onDestroy()
        stopPlayback()
        exoPlayer?.release()
        exoPlayer = null
    }
}
