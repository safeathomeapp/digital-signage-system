print("RUNNING production_app.py FROM:", __file__)

# Enhanced Flask Backend with Device-Specific Content Management
from flask import Flask, request, jsonify, render_template, redirect, send_from_directory
from werkzeug.utils import secure_filename
import sqlite3
import os
from datetime import datetime, date, timedelta, timezone
import json
import socket
import logging
from waitress import serve
import time
import secrets
import hmac
import threading
import hashlib

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this-in-production'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max
# Device token store (file-backed)
TOKEN_STORE_PATH = os.environ.get('SIGNAGE_TOKEN_STORE', 'device_tokens.json')
_TOKEN_LOCK = threading.Lock()

def get_db_connection():
    conn = sqlite3.connect('signage.db')
    conn.row_factory = sqlite3.Row
    return conn

def _get_setting(key: str, default: str | None = None) -> str | None:
    try:
        conn = get_db_connection()
        row = conn.execute('SELECT value FROM system_settings WHERE key = ?', (key,)).fetchone()
        conn.close()
        return row['value'] if row else default
    except Exception:
        logging.exception("Failed to read system setting")
        return default

def _set_setting(key: str, value: str) -> None:
    try:
        conn = get_db_connection()
        conn.execute('INSERT INTO system_settings (key, value) VALUES (?, ?) '
                     'ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, value))
        conn.commit()
        conn.close()
    except Exception:
        logging.exception("Failed to write system setting")

def _hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode('utf-8')).hexdigest()

def _ensure_default_pin():
    env_pin = os.environ.get('SIGNAGE_ADMIN_PIN')
    if env_pin:
        _set_setting('admin_pin_hash', _hash_pin(env_pin))
        return
    if not _get_setting('admin_pin_hash'):
        _set_setting('admin_pin_hash', _hash_pin('1234'))


def _load_token_store():
    if not os.path.exists(TOKEN_STORE_PATH):
        return {}
    try:
        with open(TOKEN_STORE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f) or {}
    except Exception:
        logging.exception("Failed to load token store")
        return {}

def _save_token_store(store: dict):
    tmp_path = TOKEN_STORE_PATH + ".tmp"
    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(store, f, indent=2, sort_keys=True)
        os.replace(tmp_path, TOKEN_STORE_PATH)
    except Exception:
        logging.exception("Failed to save token store")
        # best effort cleanup
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

def _get_or_create_device_token(device_id: str, force_rotate: bool = False) -> str:
    """Idempotent unless force_rotate=True."""
    with _TOKEN_LOCK:
        store = _load_token_store()
        rec = store.get(device_id)
        if rec and (not force_rotate) and rec.get("token"):
            return rec["token"]
        token = secrets.token_urlsafe(32)
        store[device_id] = {
            "token": token,
            "issued_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "rotated": bool(force_rotate),
        }
        _save_token_store(store)
        return token

def _is_device_active(device_id: str) -> bool:
    try:
        conn = get_db_connection()
        row = conn.execute("SELECT device_id FROM devices WHERE device_id = ? AND is_active = 1", (device_id,)).fetchone()
        conn.close()
        return row is not None
    except Exception:
        logging.exception("Failed to verify device status")
        return False

def _verify_device_token(device_id: str, token: str) -> bool:
    with _TOKEN_LOCK:
        store = _load_token_store()
        rec = store.get(device_id) or {}
        stored = rec.get("token")
    if not stored:
        return False
    # constant-time compare
    try:
        return hmac.compare_digest(str(stored), str(token))
    except Exception:
        return False

def require_device_auth(fn):
    """Protect client-facing endpoints with per-device token auth."""
    from functools import wraps

    @wraps(fn)
    def wrapper(*args, **kwargs):
        device_id = (request.headers.get("X-Device-Id") or kwargs.get("device_id") or "").strip()
        token = (request.headers.get("X-Device-Token") or "").strip()

        if not device_id or not token:
            return jsonify({"error": "unauthorized", "detail": "Missing X-Device-Id or X-Device-Token"}), 401

        if not _is_device_active(device_id):
            return jsonify({"error": "forbidden", "code": "inactive_device", "detail": "Unknown or inactive device"}), 403

        if not _verify_device_token(device_id, token):
            return jsonify({"error": "forbidden", "code": "invalid_token", "detail": "Invalid token"}), 403

        return fn(*args, **kwargs)

    return wrapper

# Ensure folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('logs', exist_ok=True)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/signage_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Get server IP automatically
def get_server_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "localhost"

SERVER_IP = get_server_ip()
# Auto refresh
LAST_CONTENT_UPDATE = time.time()

# Database setup
def upgrade_database():
    """Add missing transition columns to device_content table"""
    conn = sqlite3.connect('signage.db')
    
    try:
        # Add transition_type column
        conn.execute('ALTER TABLE device_content ADD COLUMN transition_type TEXT DEFAULT "fade"')
        logger.info("Added transition_type column")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        # Add transition_duration column  
        conn.execute('ALTER TABLE device_content ADD COLUMN transition_duration REAL DEFAULT 1.0')
        logger.info("Added transition_duration column")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    conn.commit()
    conn.close()
    logger.info("Database upgrade completed")
    
def init_db():
    conn = sqlite3.connect('signage.db')
    
    # Media table (global library) - FIXED with video_duration column
    conn.execute('''
        CREATE TABLE IF NOT EXISTS media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            original_name TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_size INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            uploaded_from_ip TEXT,
            video_duration INTEGER
        )
    ''')
    
    # Add video_duration column if it doesn't exist
    try:
        conn.execute('ALTER TABLE media ADD COLUMN video_duration INTEGER')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Devices table
    conn.execute('''
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
            overlay_enabled BOOLEAN DEFAULT 1,
            overlay_position TEXT DEFAULT "top-right",
            overlay_opacity REAL DEFAULT 0.6,
            overlay_size REAL DEFAULT 0.1,
            overlay_hide_on_video BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Add overlay columns if missing
    try:
        conn.execute('ALTER TABLE devices ADD COLUMN overlay_enabled BOOLEAN DEFAULT 1')
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute('ALTER TABLE devices ADD COLUMN overlay_position TEXT DEFAULT "top-right"')
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute('ALTER TABLE devices ADD COLUMN overlay_opacity REAL DEFAULT 0.6')
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute('ALTER TABLE devices ADD COLUMN overlay_size REAL DEFAULT 0.1')
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute('ALTER TABLE devices ADD COLUMN overlay_hide_on_video BOOLEAN DEFAULT 1')
    except sqlite3.OperationalError:
        pass

    # System settings (global configuration)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')
    
    # Device-specific content assignments
    conn.execute('''
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
    overlay_enabled BOOLEAN,
    overlay_position TEXT,
            analytics_enabled BOOLEAN DEFAULT 0,
            analytics_sample_rate INTEGER DEFAULT 5,
            analytics_counter INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (media_id) REFERENCES media (id),
            FOREIGN KEY (device_id) REFERENCES devices (device_id)
        )
    ''')
    try:
        conn.execute('ALTER TABLE device_content ADD COLUMN video_duration INTEGER')
    except sqlite3.OperationalError:
        pass  # Column already exists
    try:
        conn.execute('ALTER TABLE device_content ADD COLUMN overlay_enabled BOOLEAN')
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute('ALTER TABLE device_content ADD COLUMN overlay_position TEXT')
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute('ALTER TABLE device_content ADD COLUMN analytics_enabled BOOLEAN DEFAULT 0')
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute('ALTER TABLE device_content ADD COLUMN analytics_sample_rate INTEGER DEFAULT 5')
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute('ALTER TABLE device_content ADD COLUMN analytics_counter INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass
        
    # Analytics table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS playback_analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            media_id INTEGER,
            assignment_id INTEGER,
            filename TEXT NOT NULL,
            file_type TEXT NOT NULL,
            started_at TIMESTAMP NOT NULL,
            ended_at TIMESTAMP,
            planned_duration INTEGER,
            actual_duration INTEGER,
            completed BOOLEAN DEFAULT 0,
            FOREIGN KEY (media_id) REFERENCES media (id)
        )
    ''')
    try:
        conn.execute('ALTER TABLE playback_analytics ADD COLUMN assignment_id INTEGER')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully")

# Helper functions
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi', 'webm', 'mkv'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Auto refresh
def update_content_timestamp():
    """Update the global timestamp when content changes"""
    global LAST_CONTENT_UPDATE
    LAST_CONTENT_UPDATE = time.time()
    logger.debug(f"Content timestamp updated: {LAST_CONTENT_UPDATE}")
    
# Main routes
@app.route('/')
def index():
    return render_template('index.html', server_ip=SERVER_IP)

@app.route('/devices')
def device_management():
    ##return render_template('devices.html', server_ip=SERVER_IP)
    return redirect('/')
    
@app.route('/device/<device_id>')
def device_detail(device_id):
    return render_template('device_detail.html', server_ip=SERVER_IP, device_id=device_id)

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html', server_ip=SERVER_IP)

# FIXED Upload endpoint with video duration handling
@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file selected'}), 400
        
        file = request.files['file']
        if file.filename == '' or not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type'}), 400
        
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
        unique_filename = timestamp + filename
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        
        # Save file with error handling
        try:
            file.save(file_path)
        except Exception as save_error:
            logger.error(f"File save error: {save_error}")
            return jsonify({'error': 'Failed to save file to disk'}), 500
        
        file_size = os.path.getsize(file_path)
        file_type = 'image' if filename.lower().endswith(('png', 'jpg', 'jpeg', 'gif')) else 'video'
        
        # FIXED: Get video duration from scheduling data
        video_duration = None
        scheduling_data = request.form.get('scheduling')
        if scheduling_data:
            try:
                schedule = json.loads(scheduling_data)
                video_duration = schedule.get('video_duration')
            except json.JSONDecodeError:
                pass
        
        conn = sqlite3.connect('signage.db')
        
        # FIXED: Insert media record with video duration
        cursor = conn.execute('''
            INSERT INTO media (filename, original_name, file_type, file_size, uploaded_from_ip, video_duration)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (unique_filename, filename, file_type, file_size, request.remote_addr, video_duration))
        
        media_id = cursor.lastrowid
        
        # Handle scheduling data if provided
        if scheduling_data:
            try:
                schedule = json.loads(scheduling_data)
                device_assignment = schedule.get('device_assignment')
                
                if device_assignment:
                    days_list = schedule.get('days_of_week', [])
                    # If no days specified or empty list, default to all days
                    if not days_list or len(days_list) == 0:
                        days_list = ['all']
                    days_json = json.dumps(days_list)
                    
                    # Get display duration - use video duration as minimum if available
                    display_duration = schedule.get('display_duration', 10)
                    
                    # For videos, ensure display duration is at least as long as video duration
                    if video_duration and file_type == 'video':
                        display_duration = max(display_duration, video_duration)
                        
                    if device_assignment == 'all':
                        # Assign to all existing devices
                        cursor = conn.execute('SELECT device_id FROM devices WHERE is_active = 1')
                        devices = cursor.fetchall()
                        
                        for device in devices:
                            # Get next play order for each device
                            cursor = conn.execute('''
                                SELECT COALESCE(MAX(play_order), 0) + 1 
                                FROM device_content 
                                WHERE device_id = ? AND is_active = 1
                            ''', (device[0],))
                            next_order = cursor.fetchone()[0]
                            
                            conn.execute('''
                                INSERT INTO device_content 
                                (device_id, media_id, display_duration, video_duration, days_of_week, start_date, end_date, start_time, end_time, is_active, play_order)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                            ''', (
                                device[0],
                                media_id,
                                display_duration,
                                video_duration,
                                days_json,
                                schedule.get('start_date'),
                                schedule.get('end_date'),
                                schedule.get('start_time'),
                                schedule.get('end_time'),
                                next_order
                            ))
                        
                        logger.info(f"Content {media_id} assigned to all {len(devices)} devices")
                    else:
                        # Assign to specific device
                        cursor = conn.execute('''
                            SELECT COALESCE(MAX(play_order), 0) + 1 
                            FROM device_content 
                            WHERE device_id = ? AND is_active = 1
                        ''', (device_assignment,))
                        next_order = cursor.fetchone()[0]
                        
                        conn.execute('''
                            INSERT INTO device_content 
                            (device_id, media_id, display_duration, video_duration, days_of_week, start_date, end_date, start_time, end_time, is_active, play_order)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                        ''', (
                            device_assignment,
                            media_id,
                            display_duration,
                            video_duration,
                            days_json,
                            schedule.get('start_date'),
                            schedule.get('end_date'),
                            schedule.get('start_time'),
                            schedule.get('end_time'),
                            next_order
                        ))
                        
                        logger.info(f"Content {media_id} assigned to device {device_assignment}")
            
            except json.JSONDecodeError as json_error:
                logger.warning(f"Invalid scheduling data received: {json_error}")
        
        conn.commit()
        update_content_timestamp()
        conn.close()
        
        return jsonify({'success': 'File uploaded and scheduled successfully'})
    
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

# Assign content with full scheduling data
@app.route('/api/assign-content-with-schedule', methods=['POST'])
def assign_content_with_schedule():
    try:
        data = request.get_json()
        device_id = data.get('device_id')
        media_id = data.get('media_id')
        assignment_id = data.get('assignment_id')
        
        if not device_id or not media_id:
            return jsonify({'error': 'Device ID and Media ID required'}), 400
        
        conn = sqlite3.connect('signage.db')
        
        # Get video duration from media table if it's a video
        cursor = conn.execute('SELECT file_type, video_duration FROM media WHERE id = ?', (media_id,))
        media_info = cursor.fetchone()
        
        if not media_info:
            conn.close()
            return jsonify({'error': 'Media not found'}), 400
        
        file_type, stored_video_duration = media_info
        
        # Set duration based on type
        display_duration = data.get('display_duration', 10)
        if file_type == 'video' and stored_video_duration:
            display_duration = stored_video_duration
        
        # Get next play order
        cursor = conn.execute('''
            SELECT COALESCE(MAX(play_order), 0) + 1 
            FROM device_content 
            WHERE device_id = ? AND is_active = 1
        ''', (device_id,))
        next_order = cursor.fetchone()[0]
        
        # Prepare days of week
        days_list = data.get('days_of_week', ['all'])
        days_json = json.dumps(days_list)
        
        # Create new assignment with full scheduling
        cursor = conn.execute('''
            INSERT INTO device_content 
            (device_id, media_id, display_duration, video_duration, days_of_week, 
             start_date, end_date, start_time, end_time, play_order, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        ''', (
            device_id, 
            media_id, 
            display_duration,
            stored_video_duration,
            days_json,
            data.get('start_date'),
            data.get('end_date'),
            data.get('start_time'),
            data.get('end_time'),
            next_order
        ))
        assignment_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        logger.info(f"Content {media_id} assigned to device {device_id} with scheduling")
        return jsonify({'success': 'Content assigned with scheduling', 'assignment_id': assignment_id})
    
    except Exception as e:
        logger.error(f"Error assigning content with schedule: {e}")
        return jsonify({'error': 'Failed to assign content'}), 500
        
# Enhanced Media API with status information
@app.route('/api/media')
def get_media_list():
    try:
        conn = sqlite3.connect('signage.db')
        cursor = conn.execute('''
            SELECT m.id, m.filename, m.original_name, m.file_type, m.file_size, m.created_at,
                   (SELECT COUNT(*) FROM device_content WHERE media_id = m.id AND is_active = 1) as assignment_count,
                   (SELECT MIN(start_date) FROM device_content WHERE media_id = m.id) as start_date,
                   (SELECT MAX(end_date) FROM device_content WHERE media_id = m.id) as end_date,
                   (SELECT MIN(is_active) FROM device_content WHERE media_id = m.id) as is_active
            FROM media m
            ORDER BY m.created_at DESC
        ''')
        
        media_list = []
        for row in cursor.fetchall():
            media_list.append({
                'id': row[0],
                'filename': row[1],
                'original_name': row[2],
                'file_type': row[3],
                'file_size': row[4],
                'created_at': row[5],
                'assignment_count': row[6],
                'start_date': row[7],
                'end_date': row[8],
                'is_active': bool(row[9]) if row[9] is not None else True
            })
        
        conn.close()
        return jsonify(media_list)
    
    except Exception as e:
        logger.error(f"Error getting media list: {e}")
        return jsonify({'error': 'Failed to get media list'}), 500

# Get media info
@app.route('/api/media/<int:media_id>')
def get_media_info(media_id):
    try:
        conn = sqlite3.connect('signage.db')
        cursor = conn.execute('''
            SELECT id, filename, original_name, file_type, file_size, created_at, video_duration
            FROM media
            WHERE id = ?
        ''', (media_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return jsonify({'error': 'Media not found'}), 404

        return jsonify({
            'id': row[0],
            'filename': row[1],
            'original_name': row[2],
            'file_type': row[3],
            'file_size': row[4],
            'created_at': row[5],
            'video_duration': row[6]
        })

    except Exception as e:
        logger.error(f"Error getting media info: {e}")
        return jsonify({'error': 'Failed to get media info'}), 500

# Delete media
@app.route('/api/media/<int:media_id>', methods=['DELETE'])
def delete_media(media_id):
    try:
        conn = sqlite3.connect('signage.db')

        cursor = conn.execute('SELECT filename FROM media WHERE id = ?', (media_id,))
        result = cursor.fetchone()

        if not result:
            conn.close()
            return jsonify({'error': 'Media not found'}), 404

        filename = result[0]

        conn.execute('DELETE FROM device_content WHERE media_id = ?', (media_id,))
        conn.execute('DELETE FROM playback_analytics WHERE media_id = ?', (media_id,))
        conn.execute('DELETE FROM media WHERE id = ?', (media_id,))

        conn.commit()
        update_content_timestamp()
        conn.close()

        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(file_path):
            os.remove(file_path)

        logger.info(f"Media {media_id} ({filename}) deleted completely")
        return jsonify({'success': 'Media deleted successfully'})

    except Exception as e:
        logger.error(f"Error deleting media: {e}")
        return jsonify({'error': 'Failed to delete media'}), 500

@app.route('/api/devices')
def get_devices():
    try:
        conn = get_db_connection()
        cursor = conn.execute('''
            SELECT d.device_id, d.device_name, d.custom_name, d.location, d.last_checkin,
                   d.is_active, d.ip_address, d.app_version, d.created_at,
                   d.overlay_enabled, d.overlay_position, d.overlay_opacity, d.overlay_size,
                   d.overlay_hide_on_video,
                   COUNT(dc.id) as content_count
            FROM devices d
            LEFT JOIN device_content dc ON d.device_id = dc.device_id
                AND dc.is_active = 1
                AND dc.media_id IN (SELECT id FROM media)
            GROUP BY d.device_id, d.device_name, d.custom_name, d.location, d.last_checkin,
                     d.is_active, d.ip_address, d.app_version, d.created_at
            ORDER BY d.last_checkin DESC
        ''')

        token_store = _load_token_store()
        devices = []
        for row in cursor.fetchall():
                devices.append({
                    'device_id': row['device_id'],
                    'token_registered': bool(token_store.get(row['device_id'], {}).get('token')),
                    'device_name': row['device_name'],
                    'custom_name': row['custom_name'],
                    'location': row['location'],
                    'last_checkin': row['last_checkin'],
                    'is_active': bool(row['is_active']),
                    'ip_address': row['ip_address'],
                    'app_version': row['app_version'],
                    'created_at': row['created_at'],
                    'overlay_enabled': bool(row['overlay_enabled']) if row['overlay_enabled'] is not None else True,
                    'overlay_position': row['overlay_position'] or 'top-right',
                    'overlay_opacity': float(row['overlay_opacity']) if row['overlay_opacity'] is not None else 0.6,
                    'overlay_size': float(row['overlay_size']) if row['overlay_size'] is not None else 0.1,
                    'overlay_hide_on_video': bool(row['overlay_hide_on_video']) if row['overlay_hide_on_video'] is not None else True,
                    'content_count': row['content_count'],
                    'display_name': row['custom_name'] if row['custom_name'] else row['device_name']
                })

        conn.close()
        return jsonify(devices)

    except Exception as e:
        logger.error(f"Error getting devices: {e}")
        return jsonify({'error': 'Failed to get devices'}), 500

# Update device information
@app.route('/api/device/<device_id>', methods=['PUT'])
def update_device(device_id):
    try:
        data = request.get_json() or {}
        custom_name = data.get('custom_name', '')
        location = data.get('location', '')

        conn = sqlite3.connect('signage.db')
        conn.execute('''
            UPDATE devices
            SET custom_name = ?, location = ?
            WHERE device_id = ?
        ''', (custom_name, location, device_id))
        conn.commit()
        conn.close()

        logger.info(f"Device {device_id} updated: name='{custom_name}', location='{location}'")
        return jsonify({'success': 'Device updated successfully'})

    except Exception as e:
        logger.error(f"Error updating device: {e}")
        return jsonify({'error': 'Failed to update device'}), 500

# Update device overlay settings
@app.route('/api/device/<device_id>/overlay', methods=['PUT'])
def update_device_overlay(device_id):
    try:
        data = request.get_json() or {}
        overlay_enabled = 1 if data.get('overlay_enabled', True) else 0
        overlay_position = data.get('overlay_position', 'top-right')
        overlay_opacity = float(data.get('overlay_opacity', 0.6))
        overlay_size = float(data.get('overlay_size', 0.1))
        overlay_hide_on_video = 1 if data.get('overlay_hide_on_video', True) else 0

        conn = sqlite3.connect('signage.db')
        conn.execute('''
            UPDATE devices
            SET overlay_enabled = ?, overlay_position = ?, overlay_opacity = ?,
                overlay_size = ?, overlay_hide_on_video = ?
            WHERE device_id = ?
        ''', (
            overlay_enabled,
            overlay_position,
            overlay_opacity,
            overlay_size,
            overlay_hide_on_video,
            device_id
        ))
        conn.commit()
        conn.close()

        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"Overlay save error: {e}")
        return jsonify({'error': 'Failed to save overlay settings'}), 500

# Activate device
@app.route('/api/device/<device_id>/activate', methods=['PUT'])
def activate_device(device_id):
    try:
        conn = sqlite3.connect('signage.db')
        cur = conn.execute(
            'UPDATE devices SET is_active = 1, last_checkin = ? WHERE device_id = ?',
            (datetime.now(), device_id)
        )
        conn.commit()
        conn.close()

        if cur.rowcount == 0:
            return jsonify({'error': 'not_found', 'detail': 'Device not found'}), 404

        logger.info(f"Device {device_id} activated")
        return jsonify({'success': True, 'device_id': device_id, 'is_active': True}), 200

    except Exception as e:
        logger.error(f"Error activating device {device_id}: {e}")
        return jsonify({'error': 'server_error', 'detail': 'Failed to activate device'}), 500

# Get device content assignments
@app.route('/api/device/<device_id>/content')
def get_device_content(device_id):
    try:
        conn = sqlite3.connect('signage.db')
        cursor = conn.execute('''
            SELECT dc.id as assignment_id, dc.media_id, dc.display_duration,
                   dc.play_order,
                   dc.days_of_week, dc.start_date, dc.end_date,
                   dc.start_time, dc.end_time,
                   dc.is_active, dc.transition_type, dc.transition_duration,
                   dc.analytics_enabled, dc.analytics_sample_rate,
                   dc.overlay_enabled, dc.overlay_position,
                   m.filename, m.original_name, m.file_type, m.video_duration
            FROM device_content dc
            JOIN media m ON dc.media_id = m.id
            WHERE dc.device_id = ?
            ORDER BY dc.play_order ASC, dc.created_at ASC
        ''', (device_id,))

        content = []
        for row in cursor.fetchall():
            content.append({
                'assignment_id': row[0],
                'media_id': row[1],
                'display_duration': row[2],
                'play_order': row[3] or 0,
                'days_of_week': row[4],
                'start_date': row[5],
                'end_date': row[6],
                'start_time': row[7],
                'end_time': row[8],
                'is_paused': not bool(row[9]),
                'transition_type': row[10] or 'fade',
                'transition_duration': row[11] or 1.0,
                'analytics_enabled': bool(row[12]) if row[12] is not None else False,
                'analytics_sample_rate': row[13] if row[13] is not None else 5,
                'overlay_enabled': None if row[14] is None else bool(row[14]),
                'overlay_position': row[15],
                'filename': row[16],
                'original_name': row[17],
                'file_type': row[18],
                'video_duration': row[19]
            })

        conn.close()
        return jsonify(content)

    except Exception as e:
        logger.error(f"Error getting device content: {e}")
        return jsonify({'error': 'Failed to get device content'}), 500

# Update media schedule
@app.route('/api/media/<int:media_id>/schedule', methods=['PUT'])
def update_media_schedule(media_id):
    try:
        data = request.get_json()
        
        conn = sqlite3.connect('signage.db')
        
        # Get days of week, default to 'all' if empty
        days_list = data.get('days_of_week', [])
        if not days_list or len(days_list) == 0:
            days_list = ['all']
        days_json = json.dumps(days_list)
        
        # Update all device_content records for this media
        overlay_enabled = data.get('overlay_enabled')
        overlay_position = data.get('overlay_position')
        analytics_enabled = bool(data.get('analytics_enabled', False))
        analytics_sample_rate = int(data.get('analytics_sample_rate') or 5)

        conn.execute('''
            UPDATE device_content 
            SET days_of_week = ?, display_duration = ?, start_time = ?, end_time = ?, 
                start_date = ?, end_date = ?, transition_type = ?, transition_duration = ?,
                analytics_enabled = ?, analytics_sample_rate = ?,
                overlay_enabled = ?, overlay_position = ?
            WHERE media_id = ?
        ''', (
            days_json,
            data.get('display_duration', 10),
            data.get('start_time'),
            data.get('end_time'),
            data.get('start_date'),
            data.get('end_date'),
            data.get('transition_type', 'fade'),
            data.get('transition_duration', 1.0),
            1 if analytics_enabled else 0,
            analytics_sample_rate,
            None if overlay_enabled is None else (1 if overlay_enabled else 0),
            overlay_position,
            media_id
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Media {media_id} schedule updated with transitions")
        return jsonify({'success': 'Schedule updated successfully'})
    
    except Exception as e:
        logger.error(f"Error updating device content schedule: {e}")
        return jsonify({'error': 'Failed to update schedule'}), 500

# Update device content schedule (per assignment)
@app.route('/api/device-content/<int:assignment_id>/schedule', methods=['PUT'])
def update_device_content_schedule(assignment_id):
    try:
        data = request.get_json()

        conn = sqlite3.connect('signage.db')

        days_list = data.get('days_of_week', [])
        if not days_list or len(days_list) == 0:
            days_list = ['all']
        days_json = json.dumps(days_list)

        overlay_enabled = data.get('overlay_enabled')
        overlay_position = data.get('overlay_position')
        analytics_enabled = bool(data.get('analytics_enabled', False))
        analytics_sample_rate = int(data.get('analytics_sample_rate') or 5)

        conn.execute('''
            UPDATE device_content
            SET days_of_week = ?, display_duration = ?, start_time = ?, end_time = ?,
                start_date = ?, end_date = ?, transition_type = ?, transition_duration = ?,
                analytics_enabled = ?, analytics_sample_rate = ?,
                overlay_enabled = ?, overlay_position = ?
            WHERE id = ?
        ''', (
            days_json,
            data.get('display_duration', 10),
            data.get('start_time'),
            data.get('end_time'),
            data.get('start_date'),
            data.get('end_date'),
            data.get('transition_type', 'fade'),
            data.get('transition_duration', 1.0),
            1 if analytics_enabled else 0,
            analytics_sample_rate,
            None if overlay_enabled is None else (1 if overlay_enabled else 0),
            overlay_position,
            assignment_id
        ))

        conn.commit()
        conn.close()

        logger.info(f"Device content {assignment_id} schedule updated with transitions")
        return jsonify({'success': 'Schedule updated successfully'})

    except Exception as e:
        logger.error(f"Error updating device content schedule: {e}")
        return jsonify({'error': 'Failed to update schedule'}), 500

# Reorder device content
@app.route('/api/device/reorder-content', methods=['PUT'])
def reorder_device_content():
    try:
        data = request.get_json() or {}
        device_id = data.get('device_id')
        content_order = data.get('content_order') or []

        if not device_id:
            return jsonify({'error': 'Device ID required'}), 400

        conn = sqlite3.connect('signage.db')
        for item in content_order:
            conn.execute('''
                UPDATE device_content
                SET play_order = ?
                WHERE id = ? AND device_id = ?
            ''', (item.get('play_order'), item.get('assignment_id'), device_id))

        conn.commit()
        update_content_timestamp()
        conn.close()

        logger.info(f"Content reordered for device {device_id}")
        return jsonify({'success': 'Content reordered successfully'})

    except Exception as e:
        logger.error(f"Error reordering content: {e}")
        return jsonify({'error': 'Failed to reorder content'}), 500

# Remove content from device
@app.route('/api/remove-content/<int:assignment_id>', methods=['DELETE'])
def remove_content(assignment_id):
    try:
        conn = sqlite3.connect('signage.db')
        conn.execute('DELETE FROM device_content WHERE id = ?', (assignment_id,))
        conn.commit()
        update_content_timestamp()
        conn.close()

        logger.info(f"Content assignment {assignment_id} removed")
        return jsonify({'success': 'Content assignment removed'})

    except Exception as e:
        logger.error(f"Error removing content: {e}")
        return jsonify({'error': 'Failed to remove content'}), 500

# Toggle device content pause
@app.route('/api/device-content/<int:assignment_id>/pause', methods=['PUT'])
def toggle_device_content_pause(assignment_id):
    try:
        conn = sqlite3.connect('signage.db')
        cursor = conn.execute('SELECT is_active FROM device_content WHERE id = ?', (assignment_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return jsonify({'error': 'Content assignment not found'}), 404

        new_status = 0 if row[0] else 1
        conn.execute('UPDATE device_content SET is_active = ? WHERE id = ?', (new_status, assignment_id))
        conn.commit()
        conn.close()

        return jsonify({'success': True, 'is_paused': not bool(new_status)})

    except Exception as e:
        logger.error(f"Error toggling content pause: {e}")
        return jsonify({'error': 'Failed to toggle content'}), 500
        
# Delete device
@app.route('/api/device/<device_id>', methods=['DELETE'])
def delete_device(device_id):
    try:
        conn = sqlite3.connect('signage.db')
        
        # Delete device content assignments first
        conn.execute('DELETE FROM device_content WHERE device_id = ?', (device_id,))
        
        # Delete device record
        cursor = conn.execute('DELETE FROM devices WHERE device_id = ?', (device_id,))
        
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({'error': 'Device not found'}), 404
        
        conn.commit()
        conn.close()
        
        logger.info(f"Device {device_id} deleted")
        return jsonify({'success': 'Device deleted successfully'})
    
    except Exception as e:
        logger.error(f"Error deleting device: {e}")
        return jsonify({'error': 'Failed to delete device'}), 500

# System settings
@app.route('/api/system/settings')
def get_system_settings():
    try:
        logo_filename = _get_setting('overlay_logo_filename')
        overlay_logo_url = None
        if logo_filename:
            overlay_logo_url = f'http://{SERVER_IP}:5000/uploads/{logo_filename}'
        return jsonify({
            'overlay_logo_url': overlay_logo_url
        })
    except Exception as e:
        logger.error(f"System settings error: {e}")
        return jsonify({'error': 'Failed to get settings'}), 500

@app.route('/api/system/overlay-logo', methods=['POST'])
def upload_overlay_logo():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        file = request.files['file']
        if not file or file.filename == '':
            return jsonify({'error': 'No file provided'}), 400

        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        stored_name = f'overlay_logo_{timestamp}_{filename}'
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], stored_name)
        file.save(save_path)

        _set_setting('overlay_logo_filename', stored_name)

        return jsonify({
            'success': True,
            'url': f'http://{SERVER_IP}:5000/uploads/{stored_name}'
        })

    except Exception as e:
        logger.error(f"Overlay logo upload error: {e}")
        return jsonify({'error': 'Failed to upload overlay logo'}), 500

@app.route('/api/system/pin', methods=['PUT'])
def update_admin_pin():
    try:
        data = request.get_json() or {}
        pin = str(data.get('pin', '')).strip()
        if len(pin) < 4:
            return jsonify({'error': 'PIN must be at least 4 digits'}), 400
        _set_setting('admin_pin_hash', _hash_pin(pin))
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"PIN update error: {e}")
        return jsonify({'error': 'Failed to update PIN'}), 500
# Add this new endpoint to your production_app.py file

# Database cleanup endpoint
@app.route('/api/system/cleanup', methods=['POST'])
def cleanup_database():
    """Clean up orphaned device_content records"""
    try:
        conn = sqlite3.connect('signage.db')
        
        # Delete device_content records where the media no longer exists
        cursor = conn.execute('''
            DELETE FROM device_content 
            WHERE media_id NOT IN (SELECT id FROM media)
        ''')
        orphaned_content = cursor.rowcount
        
        # Delete device_content records where the device no longer exists
        cursor = conn.execute('''
            DELETE FROM device_content 
            WHERE device_id NOT IN (SELECT device_id FROM devices)
        ''')
        orphaned_devices = cursor.rowcount
        
        # Delete analytics records where media no longer exists
        cursor = conn.execute('''
            DELETE FROM playback_analytics 
            WHERE media_id NOT IN (SELECT id FROM media)
        ''')
        orphaned_analytics = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        logger.info(f"Database cleanup: {orphaned_content} orphaned content, {orphaned_devices} orphaned device assignments, {orphaned_analytics} orphaned analytics")
        
        return jsonify({
            'success': True,
            'orphaned_content_removed': orphaned_content,
            'orphaned_device_assignments_removed': orphaned_devices,
            'orphaned_analytics_removed': orphaned_analytics
        })
    
    except Exception as e:
        logger.error(f"Database cleanup error: {e}")
        return jsonify({'error': 'Failed to cleanup database'}), 500

# Playback analytics event ingest (device -> server)
@app.route('/api/analytics/event', methods=['POST'])
@require_device_auth
def ingest_playback_event():
    try:
        data = request.get_json() or {}
        device_id = (request.headers.get("X-Device-Id") or "").strip()

        media_id = data.get('media_id')
        assignment_id = data.get('assignment_id')
        filename = data.get('filename', '')
        file_type = data.get('file_type', '')
        started_at = data.get('started_at')
        ended_at = data.get('ended_at')
        planned_duration = data.get('planned_duration')
        actual_duration = data.get('actual_duration')
        completed = bool(data.get('completed', True))

        if not media_id or not filename or not file_type or not assignment_id:
            return jsonify({'error': 'media_id, assignment_id, filename, file_type required'}), 400

        # Normalize timestamps if missing
        now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        if not started_at:
            started_at = now_iso
        if not ended_at:
            ended_at = now_iso

        conn = sqlite3.connect('signage.db')

        # Check analytics settings for this assignment
        row = conn.execute('''
            SELECT analytics_enabled, analytics_sample_rate, analytics_counter
            FROM device_content
            WHERE id = ? AND device_id = ?
        ''', (assignment_id, device_id)).fetchone()

        if not row:
            conn.close()
            return jsonify({'error': 'assignment_not_found'}), 400

        analytics_enabled, analytics_sample_rate, analytics_counter = row
        if not bool(analytics_enabled):
            conn.close()
            return jsonify({'success': True, 'skipped': 'disabled'}), 200

        sample_rate = int(analytics_sample_rate or 1)
        if sample_rate < 1:
            sample_rate = 1

        new_counter = int(analytics_counter or 0) + 1
        conn.execute('UPDATE device_content SET analytics_counter = ? WHERE id = ?', (new_counter, assignment_id))

        if sample_rate > 1 and (new_counter % sample_rate) != 0:
            conn.commit()
            conn.close()
            return jsonify({'success': True, 'skipped': 'sampled'}), 200

        conn.execute('''
            INSERT INTO playback_analytics
            (device_id, media_id, assignment_id, filename, file_type, started_at, ended_at,
             planned_duration, actual_duration, completed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            device_id,
            media_id,
            assignment_id,
            filename,
            file_type,
            started_at,
            ended_at,
            planned_duration,
            actual_duration,
            1 if completed else 0
        ))
        conn.commit()
        conn.close()

        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Analytics ingest error: {e}")
        return jsonify({'error': 'Failed to ingest analytics'}), 500

# Device playlist for Android client
@app.route('/api/playlist/<device_id>')
@require_device_auth
def get_playlist(device_id):
    logger.info("HIT get_playlist() production_app.py build=2026-02-08")
    try:
        conn = get_db_connection()

        conn.execute('''
            UPDATE devices
            SET last_checkin = ?, ip_address = ?
            WHERE device_id = ?
        ''', (datetime.now(), request.remote_addr, device_id))
        conn.commit()

        now = datetime.now()
        today = now.date()
        current_time = now.time()
        current_day = today.strftime('%a').lower()

        cursor = conn.execute('''
            SELECT dc.id as assignment_id, dc.media_id, m.filename, m.file_type,
                   dc.display_duration,
                   dc.days_of_week, dc.start_date, dc.end_date,
                   dc.start_time, dc.end_time,
                   dc.play_order, dc.transition_type, dc.transition_duration,
                   dc.analytics_enabled, dc.analytics_sample_rate,
                   dc.overlay_enabled, dc.overlay_position
            FROM device_content dc
            JOIN media m ON dc.media_id = m.id
            WHERE dc.device_id = ?
              AND dc.is_active = 1
              AND (dc.start_date IS NULL OR dc.start_date <= ?)
              AND (dc.end_date   IS NULL OR dc.end_date   >= ?)
            ORDER BY dc.play_order, dc.created_at
        ''', (device_id, today, today))

        playlist = []
        for row in cursor.fetchall():
            (assignment_id, media_id, filename, file_type, duration,
             days_json, start_date, end_date, start_time_str, end_time_str,
             play_order, transition_type, transition_duration,
             analytics_enabled, analytics_sample_rate,
             overlay_enabled, overlay_position) = row

            try:
                days_of_week = json.loads(days_json) if days_json else ['all']
            except Exception:
                days_of_week = ['all']

            day_matches = (
                'all' in days_of_week or
                current_day in days_of_week or
                (current_day in ['mon', 'tue', 'wed', 'thu', 'fri'] and 'weekdays' in days_of_week) or
                (current_day in ['sat', 'sun'] and 'weekends' in days_of_week)
            )

            time_matches = True
            if start_time_str and end_time_str:
                start_t = datetime.strptime(start_time_str, "%H:%M:%S").time() if len(start_time_str) > 5 else datetime.strptime(start_time_str, "%H:%M").time()
                end_t = datetime.strptime(end_time_str, "%H:%M:%S").time() if len(end_time_str) > 5 else datetime.strptime(end_time_str, "%H:%M").time()
                time_matches = start_t <= current_time <= end_t

            if day_matches and time_matches:
                playlist.append({
                    'id': media_id,
                    'assignment_id': assignment_id,
                    'filename': filename,
                    'file_type': file_type,
                    'display_duration': duration,
                    'play_order': play_order or 0,
                    'transition_type': transition_type or 'fade',
                    'transition_duration': transition_duration or 1.0,
                    'analytics_enabled': bool(analytics_enabled) if analytics_enabled is not None else False,
                    'analytics_sample_rate': analytics_sample_rate if analytics_sample_rate is not None else 5,
                    'overlay_enabled': None if overlay_enabled is None else bool(overlay_enabled),
                    'overlay_position': overlay_position,
                    'url': f'http://{SERVER_IP}:5000/uploads/{filename}'
                })

        device_row = conn.execute('''
            SELECT overlay_enabled, overlay_position, overlay_opacity, overlay_size, overlay_hide_on_video
            FROM devices
            WHERE device_id = ?
        ''', (device_id,)).fetchone()

        logo_filename = _get_setting('overlay_logo_filename')
        overlay_url = f'http://{SERVER_IP}:5000/uploads/{logo_filename}' if logo_filename else ''

        overlay = {
            'enabled': bool(device_row['overlay_enabled']) if device_row and device_row['overlay_enabled'] is not None else True,
            'position': device_row['overlay_position'] if device_row and device_row['overlay_position'] else 'top-right',
            'opacity': float(device_row['overlay_opacity']) if device_row and device_row['overlay_opacity'] is not None else 0.6,
            'size': float(device_row['overlay_size']) if device_row and device_row['overlay_size'] is not None else 0.1,
            'hide_on_video': bool(device_row['overlay_hide_on_video']) if device_row and device_row['overlay_hide_on_video'] is not None else True,
            'url': overlay_url
        }

        conn.close()
        return jsonify({
            'device_id': device_id,
            'overlay': overlay,
            'playlist': playlist
        }), 200

    except Exception as e:
        logger.error(f"Error serving device playlist: {e}")
        return jsonify({'error': 'Failed to get playlist'}), 500

# File serving for uploads
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except Exception as e:
        logger.error(f"File serve error: {e}")
        return "File not found", 404

# Analytics summary for a media item (with per-device breakdown)
@app.route('/api/analytics/media/<int:media_id>')
def analytics_media_summary(media_id):
    try:
        date_from = request.args.get('from')
        date_to = request.args.get('to')

        where_clauses = ['media_id = ?']
        params = [media_id]

        if date_from:
            where_clauses.append("date(started_at) >= date(?)")
            params.append(date_from)
        if date_to:
            where_clauses.append("date(started_at) <= date(?)")
            params.append(date_to)

        where_sql = " AND ".join(where_clauses)

        conn = sqlite3.connect('signage.db')
        conn.row_factory = sqlite3.Row

        summary = conn.execute(f'''
            SELECT
                COUNT(*) as plays,
                SUM(COALESCE(actual_duration, 0)) as total_seconds,
                COUNT(DISTINCT device_id) as unique_devices
            FROM playback_analytics
            WHERE {where_sql}
        ''', params).fetchone()

        per_device = conn.execute(f'''
            SELECT
                device_id,
                COUNT(*) as plays,
                SUM(COALESCE(actual_duration, 0)) as total_seconds
            FROM playback_analytics
            WHERE {where_sql}
            GROUP BY device_id
            ORDER BY total_seconds DESC
        ''', params).fetchall()

        conn.close()

        return jsonify({
            'media_id': media_id,
            'from': date_from,
            'to': date_to,
            'plays': summary['plays'] or 0,
            'total_seconds': summary['total_seconds'] or 0,
            'unique_devices': summary['unique_devices'] or 0,
            'per_device': [dict(row) for row in per_device]
        })
    except Exception as e:
        logger.error(f"Analytics summary error: {e}")
        return jsonify({'error': 'Failed to fetch analytics'}), 500
 
# Add these routes to your production_app.py

@app.route('/api/device-content/<int:assignment_id>/transition', methods=['PUT'])
def update_content_transition(assignment_id):
    """Update transition settings for content assignment"""
    try:
        data = request.json
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE device_content 
            SET transition_type = ?, transition_duration = ?
            WHERE id = ?
        ''', (
            data.get('transition_type', 'fade'),
            data.get('transition_duration', 1.0),
            assignment_id
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'Transition settings updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/device/<device_id>/transitions', methods=['PUT'])
def update_device_transitions(device_id):
    """Update transition settings for all content on a device"""
    try:
        data = request.json
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE device_content 
            SET transition_type = ?, transition_duration = ?
            WHERE device_id = ?
        ''', (
            data.get('transition_type', 'fade'),
            data.get('transition_duration', 1.0),
            device_id
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'Device transition settings updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
        
@app.route('/api/register', methods=['POST'])
def register_device():
    """One-time device registration to obtain a per-device token."""
    data = request.get_json(silent=True) or {}
    device_id = (data.get('device_id') or request.headers.get('X-Device-Id') or "").strip()

    if not device_id:
        return jsonify({'error': 'bad_request', 'detail': 'device_id required'}), 400

    try:
        conn = get_db_connection()
        row = conn.execute(
            'SELECT device_id, is_active FROM devices WHERE device_id = ?',
            (device_id,)
        ).fetchone()

        if row is None:
            conn.execute('''
                INSERT INTO devices (device_id, device_name, last_checkin, is_active, ip_address)
                VALUES (?, ?, ?, 0, ?)
            ''', (device_id, f'Device {device_id[:8]}', datetime.now(), request.remote_addr))
            conn.commit()
            conn.close()
            return jsonify({
                'error': 'forbidden',
                'code': 'pending_approval',
                'detail': 'Device created but inactive. Approve/activate in admin UI.'
            }), 403

        if int(row['is_active']) != 1:
            conn.execute(
                'UPDATE devices SET last_checkin = ?, ip_address = ? WHERE device_id = ?',
                (datetime.now(), request.remote_addr, device_id)
            )
            conn.commit()
            conn.close()
            return jsonify({
                'error': 'forbidden',
                'code': 'pending_approval',
                'detail': 'Device inactive. Approve/activate in admin UI.'
            }), 403

        conn.execute(
            'UPDATE devices SET last_checkin = ?, ip_address = ? WHERE device_id = ?',
            (datetime.now(), request.remote_addr, device_id)
        )
        conn.commit()
        conn.close()

        token = _get_or_create_device_token(device_id)
        return jsonify({'device_id': device_id, 'token': token}), 200

    except Exception:
        logger.exception('Registration failed')
        return jsonify({'error': 'server_error'}), 500

if __name__ == '__main__':
    init_db()
    upgrade_database()
    _ensure_default_pin()
    print(f"🚀 Digital Signage Server starting on: {SERVER_IP}:5000")
    print(f"📱 Android TVs connect to: http://{SERVER_IP}:5000")
    print(f"🌐 Upload from any PC: http://{SERVER_IP}:5000")
    
    # Use Waitress for production
    serve(app, host='0.0.0.0', port=5000, threads=4)
