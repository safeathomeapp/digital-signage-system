# Digital Signage System – Project Handover

## Overview

This project is a **LAN-only digital signage system** consisting of:

- **Android TV / Fire TV app (Kotlin)**
- **Local Flask server (Python)**

The system is intentionally **offline-first**, **stateless**, and designed for **local-network deployments** (clubs, venues, halls).  
Cloud hosting, auth hardening, and kiosk lockdown are explicitly deferred.

This README is a **handover + reset document** so a new chat or developer can resume work with full context.

---

## Architecture

### Android TV App
- Language: **Kotlin**
- Package: `com.yourcompany.signagefiretv`
- UI: `AppCompatActivity` (TV-safe)
- Networking: `HttpURLConnection`
- Image loading: **Glide**
- Storage: `SharedPreferences`

Responsibilities:
- Generate and persist a unique `device_id`
- Register with the server
- Store a per-device token
- Fetch a **device-specific playlist**
- Display images/videos fullscreen
- Retry + offline-safe behaviour

### Flask Server
- Python 3.13+
- Framework: **Flask**
- WSGI: **Waitress**
- DB: **SQLite**
- Network: LAN only (`0.0.0.0:5000`)

Responsibilities:
- Device registration + approval
- Per-device token issuance
- Playlist generation
- Media upload & scheduling
- Admin web UI

---

## Current Status (Confirmed Working)

### ✅ Registration & Approval Flow

**Client → Server contract is now stable.**

1. Device sends:
   ```json
   POST /api/register
   { "device_id": "uuid" }
   ```

2. Server behaviour:
   - New device → created as **inactive**
   - Returns `403 pending_approval`
   - Device shows “Pending approval”

3. Admin UI:
   - Lists pending devices
   - **Approve** button activates device

4. Device re-registers:
   - Receives token
   - Token stored locally
   - Device proceeds to playlist fetch

This has been fully validated via **PowerShell**, **browser UI**, and **Flask logs**.

---

## Playlist API Contract (FINAL – DO NOT CHANGE)

### Endpoint
```
GET /api/playlist/<device_id>
Headers:
  X-Device-Id
  X-Device-Token
```

### Response (ALWAYS wrapped)

```json
{
  "device_id": "test-device-001",
  "server_ip": "192.168.1.143",
  "updated_at": "2026-02-07T01:42:13.189997",
  "playlist": [
    {
      "id": 1,
      "filename": "image.jpg",
      "file_type": "image",
      "display_duration": 10,
      "play_order": 1,
      "transition_type": "fade",
      "transition_duration": 1.0,
      "url": "http://192.168.1.143:5000/uploads/image.jpg"
    }
  ]
}
```

❗ **Raw JSON arrays are no longer valid.**
❗ Client expects `playlist` field explicitly.

---

## Emulator vs Real TV Networking

| Device Type        | Server URL                 |
|--------------------|----------------------------|
| Android Emulator   | `http://10.0.2.2:5000`     |
| Physical TV        | `http://192.168.x.x:5000`  |

The Android app must be switched **before deploying to real hardware**.

---

## Files Recently Touched

### Android
- `MainActivity.kt`
  - Enforced wrapped playlist parsing
  - Token handling hardened
  - Better error/status messages
  - Server setup menu with saved URL
  - TV focus highlight for menu buttons
  - Playlist rotation by `display_duration`
  - Image scaling uses `fitCenter`
  - Image transitions: fade, slide, zoom
  - Video playback via Media3 (ExoPlayer)
  - Videos advance on playback end (not timer)
  - PIN-gated settings menu (long-press MENU/CENTER)
  - Overlay logo support (position/opacity/size from server)

### Server
- `production_app.py`
  - `/api/register` finalized
  - `/api/device/<id>/activate` added
  - `/api/playlist/<id>` now **always returns wrapper**
  - Token verification enforced
  - Playback analytics ingest + per-media summary

### Admin UI
- `templates/index.html`
  - Pending vs Active device badges
  - Approve button wired to backend
  - Overlay & PIN settings modal

### Git
- `.gitignore`
  - `device_tokens.json` excluded

---

## What Has NOT Been Tested Yet

🚫 **Live Android TV / Fire TV hardware**

Everything has been validated on:
- PowerShell (Windows)
- Browser UI
- Flask logs
- Android Emulator

**Next critical milestone is real TV testing.**

---

## Immediate Next Steps (Phase 3C)

1. **Deploy APK to real Android TV / Fire TV**
2. Update app base URL to LAN IP
3. Confirm:
   - Registration
   - Approval
   - Playlist fetch
   - Media playback (images + video)
   - Transitions
   - Overlay logo positioning/opacity
4. Validate:
   - Boot auto-start
   - Offline cache fallback
   - DPAD navigation

---

## Explicitly Deferred (Do Not Do Yet)

- ❌ Cloud hosting
- ❌ Authentication / login
- ❌ Encryption
- ❌ Kiosk lockdown
- ❌ Content playback optimisation

These belong to **Phase 4+** only.

---

## Phase Roadmap

- **Phase 3B** ✅ Emulator registration + contract lock
- **Phase 3C** ⏭ Real TV validation
- **Phase 4** Content scheduling + playback rules
- **Phase 5** Security hardening + kiosk mode

---

## Developer Notes

- This system is intentionally simple.
- LAN trust model is assumed.
- Reliability > features.
- No silent failures: log everything.
- Do not “improve” the contract without updating both sides.
- Active development branch: `dev` (smaller fixes/features land here before merging to `main`).
- Default admin PIN is `1234` unless `SIGNAGE_ADMIN_PIN` is set in environment.

---

_Last updated: 2026-02-07_
