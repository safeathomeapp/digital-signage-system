package com.yourcompany.signagefiretv

import android.app.Activity
import android.content.Context
import android.content.SharedPreferences
import android.net.Uri
import android.os.Bundle
import android.view.KeyEvent
import android.view.View
import android.view.WindowManager
import android.widget.*
import androidx.constraintlayout.widget.ConstraintLayout
import com.bumptech.glide.Glide
import com.google.android.exoplayer2.*
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
import java.util.*
import kotlin.random.Random

class MainActivity : Activity() {

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
    private var currentIndex = 0
    private var currentPlaylist: JSONArray? = null
    private var isPlaying = false
    private var settingsVisible = false

    // Device info
    private var deviceId: String = ""
    private var serverIp: String = "192.168.1.143:5000"
    private lateinit var prefs: SharedPreferences

    // Auto-refresh
    private var refreshJob: Job? = null
    private val refreshIntervalMs = 30000L // 30 seconds

    data class ContentItem(
        val id: Int,
        val filename: String,
        val fileType: String,
        val displayDuration: Int,
        val playOrder: Int,
        val transitionType: String,
        val transitionDuration: Float,
        val url: String
    )

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Full screen immersive mode for Fire TV
        setupFullScreen()

        setContentView(R.layout.activity_main)

        // Initialize preferences
        prefs = getSharedPreferences("signage_prefs", Context.MODE_PRIVATE)

        initViews()
        loadSettings()
        generateDeviceId()

        // Auto-connect on startup
        connectToServer()

        // Start auto-refresh
        startAutoRefresh()
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

        // Setup ExoPlayer
        initializePlayer()

        // Setup button listeners
        saveSettingsButton.setOnClickListener { saveSettings() }
        testConnectionButton.setOnClickListener { testConnection() }

        // Hide settings initially
        settingsLayout.visibility = View.GONE
    }

    private fun initializePlayer() {
        exoPlayer = ExoPlayer.Builder(this).build()
        videoView.player = exoPlayer
        videoView.useController = false // Disable default controls

        // Listen for playback completion
        exoPlayer?.addListener(object : Player.Listener {
            override fun onPlaybackStateChanged(playbackState: Int) {
                if (playbackState == Player.STATE_ENDED) {
                    // Video finished playing, move to next content
                    CoroutineScope(Dispatchers.Main).launch {
                        moveToNextContent()
                    }
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
        connectToServer()

        Toast.makeText(this, "Settings saved", Toast.LENGTH_SHORT).show()
    }

    private fun testConnection() {
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val testIp = serverIpInput.text.toString().trim()
                val url = URL("http://$testIp/api/system/status")
                val connection = url.openConnection() as HttpURLConnection
                connection.requestMethod = "GET"
                connection.connectTimeout = 5000
                connection.readTimeout = 5000

                val responseCode = connection.responseCode

                withContext(Dispatchers.Main) {
                    if (responseCode == 200) {
                        Toast.makeText(this@MainActivity, "Connection successful!", Toast.LENGTH_SHORT).show()
                    } else {
                        Toast.makeText(this@MainActivity, "Server error: $responseCode", Toast.LENGTH_SHORT).show()
                    }
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@MainActivity, "Connection failed: ${e.message}", Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    private fun generateDeviceId() {
        // Try to get MAC address first, fallback to stored/generated ID
        deviceId = prefs.getString("device_id", "") ?: ""

        if (deviceId.isEmpty()) {
            deviceId = try {
                // Try to get MAC address
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
                    // Fallback to random ID
                    "firetv-${Random.nextInt(100000, 999999)}"
                }
            } catch (e: Exception) {
                "firetv-${Random.nextInt(100000, 999999)}"
            }

            // Save generated device ID
            prefs.edit().putString("device_id", deviceId).apply()
        }

        updateDeviceInfo()
    }

    private fun updateDeviceInfo() {
        val currentTime = SimpleDateFormat("HH:mm:ss", Locale.getDefault()).format(Date())
        deviceInfoText.text = "Device: $deviceId | Server: $serverIp | Time: $currentTime"
    }

    private fun connectToServer() {
        statusText.text = "Connecting to server..."

        CoroutineScope(Dispatchers.IO).launch {
            try {
                val url = URL("http://$serverIp/api/playlist/$deviceId")
                val connection = url.openConnection() as HttpURLConnection
                connection.requestMethod = "GET"
                connection.connectTimeout = 10000
                connection.readTimeout = 15000

                val responseCode = connection.responseCode

                withContext(Dispatchers.Main) {
                    if (responseCode == 200) {
                        val response = connection.inputStream.bufferedReader().readText()
                        parseAndDisplayPlaylist(response)
                    } else {
                        statusText.text = "Server error: $responseCode"
                        scheduleRetry()
                    }
                }

                connection.disconnect()

            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    statusText.text = "Connection failed: ${e.message}"
                    scheduleRetry()
                }
            }
        }
    }

    private fun scheduleRetry() {
        // Retry connection in 30 seconds
        CoroutineScope(Dispatchers.Main).launch {
            delay(30000)
            connectToServer()
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

            // Start content playback
            currentIndex = 0
            startContentPlayback()

        } catch (e: Exception) {
            statusText.text = "Error parsing playlist: ${e.message}"
            scheduleRetry()
        }
    }

    private fun startContentPlayback() {
        if (currentPlaylist == null || currentPlaylist!!.length() == 0) return

        stopPlayback()
        isPlaying = true

        displayJob = CoroutineScope(Dispatchers.Main).launch {
            while (isActive && isPlaying) {
                val currentItem = currentPlaylist!!.getJSONObject(currentIndex)

                displayContent(currentItem)

                // For images, wait for display duration + transition
                if (currentItem.getString("file_type") == "image") {
                    val duration = currentItem.getInt("display_duration")
                    delay(duration * 1000L)

                    // Apply transition and move to next
                    if (currentPlaylist!!.length() > 1) {
                        val nextIndex = (currentIndex + 1) % currentPlaylist!!.length()
                        val nextItem = currentPlaylist!!.getJSONObject(nextIndex)
                        applyTransition(nextItem)
                        currentIndex = nextIndex
                    }
                } else {
                    // For videos, ExoPlayer listener handles moving to next content
                    // Just wait here to prevent immediate loop
                    delay(1000)
                }
            }
        }
    }

    private fun displayContent(contentItem: JSONObject) {
        val filename = contentItem.getString("filename")
        val fileType = contentItem.getString("file_type")
        val duration = contentItem.getInt("display_duration")
        val url = contentItem.getString("url")

        contentInfoText.text = """
            Playing: $filename (${currentIndex + 1}/${currentPlaylist?.length() ?: 1})
            Type: $fileType | Duration: ${duration}s
        """.trimIndent()

        if (fileType == "image") {
            // Show image, hide video
            imageView.visibility = View.VISIBLE
            videoView.visibility = View.GONE

            Glide.with(this)
                .load(url)
                .into(imageView)
        } else {
            // Show video, hide image
            imageView.visibility = View.GONE
            videoView.visibility = View.VISIBLE

            playVideo(url)
        }

        updateDeviceInfo()
    }

    private fun playVideo(url: String) {
        try {
            val uri = Uri.parse(url)
            val dataSourceFactory = DefaultDataSource.Factory(this)
            val mediaSource: MediaSource = ProgressiveMediaSource.Factory(dataSourceFactory)
                .createMediaSource(MediaItem.fromUri(uri))

            exoPlayer?.setMediaSource(mediaSource)
            exoPlayer?.prepare()
            exoPlayer?.play()

        } catch (e: Exception) {
            statusText.text = "Video playback error: ${e.message}"
            // Skip to next content on video error
            CoroutineScope(Dispatchers.Main).launch {
                delay(2000)
                moveToNextContent()
            }
        }
    }

    private fun moveToNextContent() {
        if (currentPlaylist != null && currentPlaylist!!.length() > 1) {
            currentIndex = (currentIndex + 1) % currentPlaylist!!.length()
            val nextItem = currentPlaylist!!.getJSONObject(currentIndex)
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

                if (nextItem.getString("file_type") == "image") {
                    Glide.with(this@MainActivity)
                        .load(nextItem.getString("url"))
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

                if (nextItem.getString("file_type") == "image") {
                    Glide.with(this@MainActivity)
                        .load(nextItem.getString("url"))
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

                if (nextItem.getString("file_type") == "image") {
                    Glide.with(this@MainActivity)
                        .load(nextItem.getString("url"))
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

                if (nextItem.getString("file_type") == "image") {
                    Glide.with(this@MainActivity)
                        .load(nextItem.getString("url"))
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

                if (nextItem.getString("file_type") == "image") {
                    Glide.with(this@MainActivity)
                        .load(nextItem.getString("url"))
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

                if (nextItem.getString("file_type") == "image") {
                    Glide.with(this@MainActivity)
                        .load(nextItem.getString("url"))
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

                if (nextItem.getString("file_type") == "image") {
                    Glide.with(this@MainActivity)
                        .load(nextItem.getString("url"))
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
                // No transition - just switch immediately
                if (nextItem.getString("file_type") == "image") {
                    Glide.with(this@MainActivity)
                        .load(nextItem.getString("url"))
                        .into(imageView)
                }
            }
        }
    }

    private fun startAutoRefresh() {
        refreshJob = CoroutineScope(Dispatchers.IO).launch {
            while (isActive) {
                delay(refreshIntervalMs)
                if (isPlaying) {
                    // Check for content updates
                    connectToServer()
                }
            }
        }
    }

    private fun stopPlayback() {
        isPlaying = false
        displayJob?.cancel()
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

    // Remote control key handling
    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        return when (keyCode) {
            KeyEvent.KEYCODE_MENU,
            KeyEvent.KEYCODE_DPAD_CENTER -> {
                if (settingsVisible) {
                    hideSettings()
                } else {
                    showSettings()
                }
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
                if (!settingsVisible && currentPlaylist != null && currentPlaylist!!.length() > 1) {
                    currentIndex = if (currentIndex > 0) currentIndex - 1 else currentPlaylist!!.length() - 1
                    displayContent(currentPlaylist!!.getJSONObject(currentIndex))
                }
                true
            }
            KeyEvent.KEYCODE_DPAD_RIGHT -> {
                if (!settingsVisible && currentPlaylist != null && currentPlaylist!!.length() > 1) {
                    currentIndex = (currentIndex + 1) % currentPlaylist!!.length()
                    displayContent(currentPlaylist!!.getJSONObject(currentIndex))
                }
                true
            }
            else -> super.onKeyDown(keyCode, event)
        }
    }

    override fun onResume() {
        super.onResume()
        setupFullScreen()
        if (!settingsVisible && currentPlaylist != null && currentPlaylist!!.length() > 0) {
            startContentPlayback()
        }
        startAutoRefresh()
    }

    override fun onPause() {
        super.onPause()
        stopPlayback()
        refreshJob?.cancel()
    }

    override fun onDestroy() {
        super.onDestroy()
        stopPlayback()
        refreshJob?.cancel()
        exoPlayer?.release()
    }
}