# Hardware TV Test Plan (Phase 3C)

Date: 2026-02-09
Owner: QA / Dev
Scope: Real Android TV / Fire TV validation on LAN

## Purpose
Validate end-to-end behavior on real TV hardware: registration, approval, playlist fetch, image/video playback, transitions, overlay, analytics, DPAD navigation, offline behavior, and restart behavior.

## Prerequisites
- Server running on LAN: `python production_app.py`
- TV and server are on the same LAN
- Known server LAN IP (e.g., `192.168.1.143`)
- APK built and available for installation
- Admin PIN known (default `1234` unless `SIGNAGE_ADMIN_PIN` set)

## Test Matrix
- Device types: Android TV, Fire TV
- Network: LAN only
- Media types: image (jpg/png), video (mp4)

## Test Data Setup
1. Upload at least 2 images and 2 videos.
2. Create 2 devices (or reuse existing) to validate per-device playlists.
3. Assign mixed media to the device with varied durations and transitions.
4. Enable analytics on at least one assignment (default sampling every 5 plays).

## Test Cases

### 1) Install and Launch
Steps:
1. Install APK on TV.
2. Launch app from TV apps list.
Expected:
- App launches fullscreen with no crashes.
- Shows registration/pending approval state if new device.

### 2) Registration and Approval
Steps:
1. Open admin UI in browser.
2. Confirm device appears as pending.
3. Approve the device.
4. Observe app re-registers and becomes active.
Expected:
- Pending badge clears.
- Device receives token and proceeds to playlist fetch.

### 3) Playlist Fetch and Render
Steps:
1. Confirm `/api/playlist/<device_id>` returns wrapped response.
2. Observe TV begins playback.
Expected:
- Playlist loads without errors.
- Images and videos render in order.

### 4) Image Playback
Steps:
1. Observe multiple images for at least 3 cycles.
Expected:
- Image scaling is fitCenter.
- No distortion or black-screen flicker.

### 5) Video Playback
Steps:
1. Observe at least two video items.
Expected:
- Video plays with audio muted (if expected) or as configured.
- Advances on playback end (not by timer).
- No stutter or decoder errors.

### 6) Transitions
Steps:
1. Use at least 3 transition types: fade, slide-left, zoom-in.
Expected:
- Transitions animate smoothly between items.
- No layout jumps or black frames.

### 7) Overlay Logo
Steps:
1. Set global overlay logo.
2. Configure per-device overlay (position/opacity/size).
Expected:
- Overlay is anchored to screen corners.
- Opacity and size match UI settings.

### 8) Scheduling Rules
Steps:
1. Create one item active now and one item outside time window.
2. Refresh playlist on TV.
Expected:
- Only active items appear.
- Outside-window items are excluded.

### 9) Analytics Sampling
Steps:
1. Enable analytics for one assignment.
2. Let item play until at least 5 cycles.
3. Query analytics endpoint.
Expected:
- Analytics events recorded at sampling rate (every 5 plays).

### 10) DPAD Navigation and Settings
Steps:
1. Navigate UI with DPAD.
2. Long-press MENU/CENTER to open settings.
3. Enter PIN if prompted.
Expected:
- Focus states visible.
- Settings opens and saves server URL.

### 11) Offline / Server Unreachable
Steps:
1. Stop server or disconnect LAN.
2. Observe app behavior for 1-2 minutes.
Expected:
- App shows offline state or retries.
- No crash. If cached playlist exists, it plays.

### 12) Reboot / Auto-start
Steps:
1. Reboot TV.
2. Launch app manually (or verify auto-start if configured).
Expected:
- App launches and resumes playback.
- If auto-start is not implemented, note as expected gap.

## Acceptance Criteria
- No crashes during 30+ minutes of playback.
- Registration and approval works reliably.
- Media playback stable for images and videos.
- Transitions and overlay render correctly.
- Analytics sampling works for at least one item.

## Logging and Evidence
- Capture logs from server (`logs/`) during test.
- Record any on-screen errors.
- Note device model, OS version, and network details.

## Findings Template
- Device:
- OS Version:
- Test Case ID:
- Observed:
- Expected:
- Severity:
- Screenshot/Log:
