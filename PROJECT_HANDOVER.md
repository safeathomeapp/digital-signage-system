# Digital Signage System – Expanded Project Handover (Senior Notes)

_Last updated: 2026-02-07_  
_Primary author: Senior maintainer (Codex)_  
_Status: Stable on LAN and emulator; hardware TV validation pending_

---

## 1) Overview

This is a LAN-only digital signage system for a social club. It is intentionally offline-first, stateless (from the client POV), and simple to operate on a local network.

It consists of:
1. Android TV / Fire TV app (Kotlin). Displays playlist content fullscreen and requests content from the local server.
2. Local Flask server (Python). Hosts admin UI, file uploads, device registration/approval, and playlist creation.

Primary goals:
1. Fast setup in local networks
2. No external dependencies
3. Simple admin UI with drag/drop upload
4. Per-device playlists with scheduling (days/times/date range)

Non-goals (explicitly deferred):
1. Cloud hosting
2. Authentication and user accounts
3. Encryption
4. Kiosk lockdown
5. Performance tuning for large fleets

---

## 2) Architecture

### 2.1 Android TV App (Client)

Role:
1. Identify and register the device with the server.
2. Fetch device-specific playlists.
3. Display media based on playlist order and timing.
4. Remain stable if network goes offline.

Key technical choices:
1. Kotlin + AppCompatActivity (TV-safe UI)
2. HttpURLConnection for networking
3. Glide for image loading
4. SharedPreferences for persistent storage

Data it persists:
1. `device_id` (generated and stored locally)
2. Device token (issued by server)
3. Optional cached playlist (if implemented in client)

Registration flow:
1. Device POSTs `device_id` to server.
2. If pending approval, it shows “Pending approval.”
3. Once approved, it gets a token and uses it for playlist calls.

---

### 2.2 Flask Server (Backend)

Role:
1. Register and approve devices.
2. Issue device tokens.
3. Store media and schedule rules.
4. Build device playlists.
5. Serve admin UI.

Runtime entry point:
1. `production_app.py` (runs with Waitress on `0.0.0.0:5000`)

Storage:
1. SQLite database: `signage.db`
2. Media files: `uploads/`
3. Device tokens: `device_tokens.json`
4. Logs: `logs/`

---

## 3) Current Status (Confirmed Working)

Registration and approval flow (stable):
1. Client -> server contract:
```
POST /api/register
{ "device_id": "uuid" }
```
2. Server behavior:
- New device -> created with `is_active=0` (inactive)
- Responds `403 pending_approval`
- Admin sees device in UI
3. Admin approves:
```
PUT /api/device/<device_id>/activate
```
4. Client re-registers:
- Server returns `{ device_id, token }`
- Client stores token for all future requests

---

## 4) Playlist API Contract (FINAL – DO NOT CHANGE)

Endpoint:
```
GET /api/playlist/<device_id>
Headers:
  X-Device-Id
  X-Device-Token
```

Response (always wrapped):
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

Important:
1. Raw JSON arrays are not valid.
2. Client expects `playlist` to exist.

---

## 5) Emulator vs Real TV Networking

Server URL per device type:
1. Android Emulator: `http://10.0.2.2:5000`
2. Physical TV: `http://192.168.x.x:5000`

Important:
1. Before deploying to real hardware, the base URL in the Android app must be updated to the local LAN IP.

---

## 6) File Structure (Server)

Key server files:
1. `production_app.py` (main server; routes, DB setup, token auth, playlist generation)
2. `templates/` (admin UI pages; main entry: `templates/index.html`)
3. `uploads/` (uploaded media served via `/uploads/<filename>`)
4. `signage.db` (SQLite DB with media, devices, assignments, analytics)
5. `device_tokens.json` (file-backed token store with atomic writes)
6. `start_server.bat` (Windows helper to launch server)

---

## 7) Server Features (Detailed)

7.1 Device registration and approval:
1. `POST /api/register`
2. Creates new devices as inactive.
3. Only active devices receive tokens.

7.2 Token authentication:
1. Tokens stored in `device_tokens.json`.
2. Verified on every playlist request using `X-Device-Id` and `X-Device-Token`.

7.3 Media upload:
1. `POST /upload`
2. Supports images and videos.
3. Saves to `uploads/`.
4. Creates entry in `media` table.

7.4 Scheduling and assignment:
1. Media can be scheduled with display duration, days of week, start/end dates, start/end times.
2. Stored in `device_content`.

7.5 Playlist assembly:
1. Filters by device_id, active assignments, date range, day-of-week, time window.
2. Builds ordered list with transitions.

---

## 8) Database Schema (Conceptual)

`devices` fields:
1. device_id
2. device_name
3. custom_name
4. location
5. last_checkin
6. is_active
7. ip_address

`media` fields:
1. filename
2. original_name
3. file_type
4. file_size
5. video_duration
6. created_at

`device_content` fields:
1. device_id
2. media_id
3. play_order
4. display_duration
5. days_of_week
6. start_date / end_date
7. start_time / end_time
8. transition_type / transition_duration

`playback_analytics`:
1. Reserved for future use (currently unused in client)

---

## 9) Admin UI (Templates)

Current behavior:
1. Index page lists devices and uploads.
2. Pending devices show a badge and “Approve” button.
3. Media can be uploaded with schedule metadata.

---

## 10) What Has NOT Been Tested

1. Live Android TV / Fire TV hardware
2. Auto-start on boot
3. Long-term caching / offline playback
4. DPAD navigation in real TV UI

---

## 11) Hardening Opportunities (Requires Approval)

No changes will be made without your approval. Below are recommended hardening tasks.

Security and auth:
1. Add basic admin password for UI
2. Rate limit registration endpoint (prevent spam)

Reliability:
1. Add graceful handling for missing uploads
2. Add heartbeat cleanup for expired devices
3. Transaction protection for file upload + DB insert

Database:
1. Add indexes on `device_content.device_id`, `media.id`
2. Add simple migrations instead of ad-hoc `ALTER TABLE`

Operational:
1. Add Windows service for auto-start
2. Add log rotation

---

## 12) Feature Expansion Ideas (Requires Approval)

Scheduling:
1. Weekly recurring schedules with templates
2. Timezone handling for each device

Playback:
1. Per-playlist transitions (fade/slide)
2. Local caching and offline playback

Admin UI:
1. Bulk upload
2. Search/filter by device/location
3. Drag-drop reordering in UI

Monitoring:
1. Health dashboard
2. Playback analytics collection from devices

---

## 13) Known Fixes / Technical Debt

1. `production_app.py` contains duplicate imports and some repeated logic.
2. `device_tokens.json` is file-based and not encrypted.
3. No strict schema migrations yet.

---

## 14) Next Steps (Phase 3C)

1. Deploy APK to real Android TV / Fire TV.
2. Update app base URL to LAN IP.
3. Validate registration, approval, playlist fetch, and media playback.

---

## 15) Developer Notes (Senior Guidance)

1. Keep the server contract stable; client depends on it.
2. Prioritize reliability over new features.
3. Don’t “improve” playlist format without updating Android client.
4. If you change schema, update both code and test on fresh DB.

---

## 16) How to Run (Server)

```
python production_app.py
```

Server runs at:
1. `http://<LAN-IP>:5000`

---

## 17) Quickstart Checklist

This is a minimal, reliable path to get the system running from scratch on a LAN.

1. Ensure Python 3.13+ is installed.
2. Create/activate a virtual environment if desired.
3. Install dependencies: `pip install -r requirements.txt`.
4. Start the server: `python production_app.py`.
5. Open admin UI in a browser on the same LAN: `http://<LAN-IP>:5000`.
6. Launch the Android TV app (emulator or real TV).
7. Wait for the device to appear in the admin UI.
8. Approve the device.
9. Upload media (drag/drop) and assign to device.
10. Confirm playlist fetch on device.

---

## 18) Troubleshooting

Server doesn’t start:
1. Verify Python version: `python --version` should be 3.13+.
2. Verify dependencies installed: `pip install -r requirements.txt`.
3. Check port availability: something else might be using `5000`.

Admin UI loads but uploads fail:
1. Check `uploads/` exists and is writable.
2. Check file size < 500MB.
3. Confirm file extension is supported.

Device stuck on “Pending approval”:
1. Ensure the device appears in the admin UI list.
2. Click Approve (activates device).
3. Device should re-register and receive a token.

Device receives 401 or 403 on playlist fetch:
1. 401 means missing token or headers.
2. 403 means inactive device or invalid token.
3. Ensure the device token is stored and sent with `X-Device-Token`.

Playlist is empty:
1. Confirm device_content assignment exists for that device.
2. Check date range and day/time filters.
3. Confirm media file exists in `uploads/`.

Media doesn’t play on TV:
1. Confirm the URL is reachable from the TV on the LAN.
2. Ensure file type is supported by the Android TV app.
3. Verify the device has permissions and enough storage.

Server IP seems wrong in playlist response:
1. Server IP is auto-detected on startup.
2. If multiple NICs exist, it may select the wrong one.
3. Manual override is a future improvement (requires changes).

---

## 19) API Reference (Server)

All endpoints are served by `production_app.py` on port `5000`.

Admin UI:
1. `GET /` (main admin UI)
2. `GET /device/<device_id>` (device detail page)
3. `GET /dashboard` (dashboard page)
4. `GET /devices` (redirects to `/`)

Device registration and auth:
1. `POST /api/register` with body `{ "device_id": "uuid" }`
2. Success response: `200` with `{ device_id, token }` if active
3. Pending response: `403` with `{ error, code: "pending_approval" }` if inactive
4. `PUT /api/device/<device_id>/activate` returns `200` with `{ success: true }` or `404` if not found

Playlist:
1. `GET /api/playlist/<device_id>`
2. Headers: `X-Device-Id`, `X-Device-Token`
3. Errors: `401` missing headers, `403` inactive device or invalid token

Media and assignment:
1. `POST /upload` with `multipart/form-data` and optional `scheduling` JSON string
2. `GET /api/media` lists media with assignment status
3. `GET /api/media/<media_id>` returns media metadata
4. `POST /api/assign-content-with-schedule` assigns media to device with scheduling
5. `PUT /api/device-content/<assignment_id>` updates display duration only
6. `PUT /api/device-content/<assignment_id>/schedule` updates schedule and transitions
7. `PUT /api/device-content/<assignment_id>/transition` updates transition fields
8. `PUT /api/device/<device_id>/transitions` bulk updates transitions on a device
9. `PUT /api/device/reorder-content` updates play_order list
10. `DELETE /api/remove-content/<assignment_id>` removes assignment

Devices:
1. `PUT /api/device/<device_id>` updates custom name and location
2. `DELETE /api/device/<device_id>` deletes device and assignments

System:
1. `GET /api/system/status` returns server stats and storage use
2. `GET /api/system/last-update` returns last content update timestamp
3. `POST /api/system/cleanup` removes orphaned DB rows

File serving:
1. `GET /uploads/<filename>` serves uploaded files

---

## 20) Database Schema (Exact SQL)

The schema below is taken directly from `production_app.py` initialization.

```sql
CREATE TABLE IF NOT EXISTS media (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    original_name TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_size INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    uploaded_from_ip TEXT,
    video_duration INTEGER
);

CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT UNIQUE NOT NULL,
    device_name TEXT NOT NULL,
    custom_name TEXT,
    location TEXT,
    last_checkin TIMESTAMP,
    is_active BOOLEAN DEFAULT 1,
    ip_address TEXT,
    app_version TEXT DEFAULT "1.0",
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS device_content (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    media_id INTEGER NOT NULL,
    start_date DATE,
    end_date DATE,
    days_of_week TEXT,
    display_duration INTEGER DEFAULT 10,
    video_duration INTEGER,
    start_time TIME,
    end_time TIME,
    is_active BOOLEAN DEFAULT 1,
    play_order INTEGER DEFAULT 0,
    transition_type TEXT DEFAULT "fade",
    transition_duration REAL DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (media_id) REFERENCES media (id),
    FOREIGN KEY (device_id) REFERENCES devices (device_id)
);

CREATE TABLE IF NOT EXISTS playback_analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    media_id INTEGER,
    filename TEXT NOT NULL,
    file_type TEXT NOT NULL,
    started_at TIMESTAMP NOT NULL,
    ended_at TIMESTAMP,
    planned_duration INTEGER,
    actual_duration INTEGER,
    completed BOOLEAN DEFAULT 0,
    FOREIGN KEY (media_id) REFERENCES media (id)
);
```

Field notes (practical usage):
1. `devices.is_active` gates token issuance and playlist access.
2. `device_content.days_of_week` stores JSON list like `['all']` or `['mon','wed']`.
3. `device_content.start_time` and `end_time` only support same-day windows.
4. `media.video_duration` is optional and used to bound display duration for videos.
5. `playback_analytics` is reserved for future use, not currently written by client.

---

## 21) Client Behaviors and Edge Cases

Registration and auth behavior:
1. New device registers with `device_id` only.
2. If inactive, server returns `403` and device should show “Pending approval.”
3. Once approved, the next register call returns a token.
4. Token must be attached to all playlist requests.

Playlist and scheduling behavior:
1. Playlist is always a wrapped JSON object with `playlist` key.
2. Day-of-week logic supports `all`, `weekdays`, `weekends`, or explicit days.
3. Time window only matches when `start_time <= now <= end_time`.
4. Overnight windows are not supported without code changes.
5. Missing or invalid `days_of_week` defaults to `['all']`.

Error handling expectations:
1. `401` means missing headers or token.
2. `403` means inactive device or invalid token.
3. `500` means server-side error; client should retry with backoff.

Performance and caching:
1. The client should cache the last known playlist if possible.
2. If media URLs fail to load, the client should retry and skip gracefully.
3. The server does not currently signal content versioning beyond `updated_at`.

---

## 22) Operational Playbook

Backups:
1. Backup `signage.db`, `device_tokens.json`, and `uploads/`.
2. Use a dated folder name to keep versions.
3. Restore by placing files back in the project root and restarting the server.

Logs:
1. Logs are written to `logs/signage_YYYYMMDD.log`.
2. If the server fails, check the newest log first.
3. Log rotation is manual; delete older logs to reclaim space.

Updates and deployments:
1. Stop the server before updating code or templates.
2. Apply changes, then restart the server.
3. Verify `/api/system/status` responds.
4. Validate a device playlist fetch after changes.

Database maintenance:
1. Use `POST /api/system/cleanup` to remove orphaned rows.
2. Avoid deleting rows manually unless you have backups.
3. Schema changes should be tested on a fresh copy of the DB.

Network and IP changes:
1. The server auto-detects its IP on startup.
2. If the LAN IP changes, restart the server so playlists return the new IP.
3. Update the Android app base URL if moving between emulator and hardware.

Safe recovery steps:
1. If content is missing, verify `uploads/` files exist.
2. If devices disappear, check `devices` table in `signage.db`.
3. If playlists are empty, confirm assignments in `device_content`.

---

## 23) References

1. Server entry point: `production_app.py`
2. Templates: `templates/`
3. Media storage: `uploads/`
4. Database: `signage.db`

---

End of document.
