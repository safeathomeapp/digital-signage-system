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
  - Overlay logo support (position/opacity/size from server, anchored to screen corners)

### Server
- `production_app.py`
  - `/api/register` finalized
  - `/api/device/<id>/activate` added
  - `/api/playlist/<id>` now **always returns wrapper**
  - Token verification enforced
  - Playback analytics ingest + per-media summary
  - Analytics daily rollup + retention scheduler
  - Analytics daily endpoint: `GET /api/analytics/daily`
  - Device block/unblock (anti-spoof): `PUT /api/device/<id>/block`, `PUT /api/device/<id>/unblock`

### Admin UI
- `templates/index.html`
  - Pending vs Active device badges (new devices highlighted)
  - Approve button wired to backend
  - Overlay & PIN settings modal (global)
  - Inline per-device settings via cog on device tiles (name/location/overlay)
  - Device settings popover (no layout push)
  - Show blocked devices toggle + blocked state badge
  - Drag-and-drop media upload zone (primary upload path)
  - Per-content analytics toggle (default every 5 plays)
  - Stats badge on assignments when analytics is enabled
  - Toast notifications for UI actions (top-center)
  - Analytics modal (daily rollup view + HTML/PDF report launch)
  - Logged-out screen with explicit login prompt

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
   - Analytics toggle + sampling (default every 5 plays)
4. Validate:
   - Boot auto-start
   - Offline cache fallback
   - DPAD navigation

## Next Engineering Tasks (UI + Analytics)

1. Spoof analytics data to validate rollups end-to-end.
2. Prevent drag/drop in Media Library from duplicating when dropping onto the upload box.
3. When assigning media, auto-enable analytics if that filename already has tracking enabled.
4. UI tidy: normalize padding/whitespace across panels.
5. Make overlay logo icon visually consistent with other device icons.
6. Simplify/tidy the device edit popover (reduce clutter).
7. Make both drag/drop boxes the same color so they read as the same action.
8. Server-side PDF generator for analytics (instead of browser print).
9. HTML report generator using Google Charts (polish output).
10. Fix rotation icon size to match other icons.
11. Stats badge: show graph icon + "stats" (remove "1/5").
12. Move "Block device" button to bottom of device popover.
13. Confirm admin PIN is only for admin UI (not reused for device access).
14. Set page height slightly shorter than full viewport (avoid taskbar overlap).

--- 

## Quick Install (Windows)

1. Run `setup_server.ps1` (creates venv, installs deps, initializes DB).
2. Run `start_server.bat` to launch the server.

If the admin PIN is forgotten, temporarily start the server with:
```
SIGNAGE_ADMIN_PIN=1234
```
Then update the PIN from Settings in the UI.

You can also run:
- `RESET_PIN.ps1`
- `RESET_PIN.bat`

---

## Explicitly Deferred (Do Not Do Yet)

- ❌ Cloud hosting
- ❌ Authentication / login
- ❌ Encryption
- ❌ Kiosk lockdown
- ❌ Content playback optimisation

These belong to **Phase 4+** only.

## Future Exploration (Not Yet Started)

- Docker/hosted server option (requires stronger security/authentication before any public exposure).

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

## Admin UI Access (PIN Gate)

- The admin UI is gated by a session-based PIN.
- Login prompt appears on page load.
- Logout button clears the session.
- Verify endpoint: `POST /api/system/pin/verify`

## Security Notes (LAN-Only)

- LAN trust model is assumed.
- Admin UI is PIN-gated; device APIs use per-device tokens.
- No external auth or encryption is enabled (by design).

## Device Orientation (Landscape/Portrait)

- Each device now stores a `display_orientation` value (`landscape` or `portrait`).
- Admin UI: set per device (inline card settings).
- Playlist response includes `display_orientation` so the app can adapt overlay sizing.

## Analytics Notes

- Analytics are recorded **per content assignment** only when **Record stats** is enabled.
- Sample rate defaults to **every 5 plays** (reduces noise; can be adjusted later in code if needed).
- Daily rollups are stored in `analytics_daily` and can be viewed in the Analytics modal.
- **Reports are not auto-generated.** Recommended workflow:
  - Generate **monthly summaries** per media using `GET /api/analytics/media/<media_id>?from=YYYY-MM-DD&to=YYYY-MM-DD`.
  - Use the Analytics modal to launch HTML/PDF reports (client-side rendering).
- **Future idea:** server-side PDF generation (instead of browser print).
- **Future idea:** add a backend “refresh app” command so devices can re-pull state when changes aren’t picked up (tie into offline/server unreachable handling).

---

_Last updated: 2026-02-11_
