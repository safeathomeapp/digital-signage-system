# Enhanced Flask Backend with Device-Specific Content Management
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import sqlite3
import os
from datetime import datetime, date, timedelta
import json
import socket
import logging
from waitress import serve
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this-in-production'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max

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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (media_id) REFERENCES media (id),
            FOREIGN KEY (device_id) REFERENCES devices (device_id)
        )
    ''')
    try:
        conn.execute('ALTER TABLE device_content ADD COLUMN video_duration INTEGER')
    except sqlite3.OperationalError:
        pass  # Column already exists
        
    # Analytics table
    conn.execute('''
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
        )
    ''')
    
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
    logger.info(f"Content timestamp updated: {LAST_CONTENT_UPDATE}")
    
# Main routes
@app.route('/')
def index():
    return render_template('index.html', server_ip=SERVER_IP)

@app.route('/devices')
def device_management():
    return render_template('devices.html', server_ip=SERVER_IP)

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

# Enhanced media details API
@app.route('/api/media/detailed')
def get_detailed_media_list():
    try:
        conn = sqlite3.connect('signage.db')
        cursor = conn.execute('''
            SELECT m.id, m.filename, m.original_name, m.file_type, m.file_size, m.created_at,
                   (SELECT COUNT(*) FROM device_content WHERE media_id = m.id AND is_active = 1) as assignment_count,
                   (SELECT MIN(start_date) FROM device_content WHERE media_id = m.id) as start_date,
                   (SELECT MAX(end_date) FROM device_content WHERE media_id = m.id) as end_date,
                   (SELECT MIN(is_active) FROM device_content WHERE media_id = m.id) as is_active,
                   (SELECT display_duration FROM device_content WHERE media_id = m.id LIMIT 1) as display_duration,
                   (SELECT start_time FROM device_content WHERE media_id = m.id LIMIT 1) as start_time,
                   (SELECT end_time FROM device_content WHERE media_id = m.id LIMIT 1) as end_time,
                   (SELECT days_of_week FROM device_content WHERE media_id = m.id LIMIT 1) as days_of_week
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
                'is_active': bool(row[9]) if row[9] is not None else True,
                'display_duration': row[10],
                'start_time': row[11],
                'end_time': row[12],
                'days_of_week': row[13]
            })
        
        conn.close()
        return jsonify(media_list)
    
    except Exception as e:
        logger.error(f"Error getting detailed media list: {e}")
        return jsonify({'error': 'Failed to get detailed media list'}), 500

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
        conn.execute('''
            UPDATE device_content 
            SET days_of_week = ?, display_duration = ?, start_time = ?, end_time = ?, 
                start_date = ?, end_date = ?
            WHERE media_id = ?
        ''', (
            days_json,
            data.get('display_duration', 10),
            data.get('start_time'),
            data.get('end_time'),
            data.get('start_date'),
            data.get('end_date'),
            media_id
        ))
        
        conn.commit()
        update_content_timestamp()
        conn.close()
        
        logger.info(f"Media {media_id} schedule updated")
        return jsonify({'success': 'Schedule updated successfully'})
    
    except Exception as e:
        logger.error(f"Error updating media schedule: {e}")
        return jsonify({'error': 'Failed to update schedule'}), 500

# Assign media to all devices
@app.route('/api/assign-all-devices', methods=['POST'])
def assign_all_devices():
    try:
        data = request.get_json()
        media_id = data.get('media_id')
        duration = data.get('display_duration', 10)
        
        if not media_id:
            return jsonify({'error': 'Media ID required'}), 400
        
        conn = sqlite3.connect('signage.db')
        
        # Get all active devices
        cursor = conn.execute('SELECT device_id FROM devices WHERE is_active = 1')
        devices = cursor.fetchall()
        
        assigned_count = 0
        for device in devices:
            device_id = device[0]
            
            # Check if assignment already exists
            cursor = conn.execute('''
                SELECT id FROM device_content 
                WHERE device_id = ? AND media_id = ? AND is_active = 1
            ''', (device_id, media_id))
            
            if not cursor.fetchone():
                # Get next play order
                cursor = conn.execute('''
                    SELECT COALESCE(MAX(play_order), 0) + 1 
                    FROM device_content 
                    WHERE device_id = ? AND is_active = 1
                ''', (device_id,))
                next_order = cursor.fetchone()[0]
                
                # Create new assignment
                conn.execute('''
                    INSERT INTO device_content (device_id, media_id, display_duration, play_order, is_active)
                    VALUES (?, ?, ?, ?, 1)
                ''', (device_id, media_id, duration, next_order))
                assigned_count += 1
        
        conn.commit()
        update_content_timestamp()
        conn.close()
        
        logger.info(f"Media {media_id} assigned to {assigned_count} devices")
        return jsonify({'success': f'Content assigned to {assigned_count} devices'})
    
    except Exception as e:
        logger.error(f"Error assigning to all devices: {e}")
        return jsonify({'error': 'Failed to assign to all devices'}), 500

# Toggle media active/inactive status
@app.route('/api/media/<int:media_id>/toggle', methods=['PUT'])
def toggle_media_status(media_id):
    try:
        data = request.get_json()
        is_active = data.get('is_active', True)
        
        conn = sqlite3.connect('signage.db')
        
        # Update media status in device_content table
        conn.execute('''
            UPDATE device_content 
            SET is_active = ? 
            WHERE media_id = ?
        ''', (is_active, media_id))
        
        conn.commit()
        update_content_timestamp()
        conn.close()
        
        logger.info(f"Media {media_id} status changed to {'active' if is_active else 'inactive'}")
        return jsonify({'success': 'Media status updated'})
    
    except Exception as e:
        logger.error(f"Error toggling media status: {e}")
        return jsonify({'error': 'Failed to update media status'}), 500

# Delete media completely
@app.route('/api/media/<int:media_id>', methods=['DELETE'])
def delete_media(media_id):
    try:
        conn = sqlite3.connect('signage.db')
        
        # Get filename for file deletion
        cursor = conn.execute('SELECT filename FROM media WHERE id = ?', (media_id,))
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            return jsonify({'error': 'Media not found'}), 404
        
        filename = result[0]
        
        # Delete device assignments
        conn.execute('DELETE FROM device_content WHERE media_id = ?', (media_id,))
        
        # Delete analytics records
        conn.execute('DELETE FROM playback_analytics WHERE media_id = ?', (media_id,))
        
        # Delete media record
        conn.execute('DELETE FROM media WHERE id = ?', (media_id,))
        
        conn.commit()
        update_content_timestamp()
        conn.close()
        
        # Delete physical file
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        
        logger.info(f"Media {media_id} ({filename}) deleted completely")
        return jsonify({'success': 'Media deleted successfully'})
    
    except Exception as e:
        logger.error(f"Error deleting media: {e}")
        return jsonify({'error': 'Failed to delete media'}), 500

# Device APIs
@app.route('/api/devices')
def get_devices():
    try:
        conn = sqlite3.connect('signage.db')
        cursor = conn.execute('''
            SELECT device_id, device_name, custom_name, location, last_checkin,
                   is_active, ip_address, app_version, created_at,
                   (SELECT COUNT(*) FROM device_content WHERE device_id = d.device_id AND is_active = 1) as content_count
            FROM devices d
            ORDER BY last_checkin DESC
        ''')
        
        devices = []
        for row in cursor.fetchall():
            devices.append({
                'device_id': row[0],
                'device_name': row[1],
                'custom_name': row[2],
                'location': row[3],
                'last_checkin': row[4],
                'is_active': bool(row[5]),
                'ip_address': row[6],
                'app_version': row[7],
                'created_at': row[8],
                'content_count': row[9],
                'display_name': row[2] if row[2] else row[1]
            })
        
        conn.close()
        return jsonify(devices)
    
    except Exception as e:
        logger.error(f"Error getting devices: {e}")
        return jsonify({'error': 'Failed to get devices'}), 500

# Get device content with play order (CONSOLIDATED SINGLE FUNCTION)
@app.route('/api/device/<device_id>/content')
def get_device_content(device_id):
    try:
        conn = sqlite3.connect('signage.db')
        cursor = conn.execute('''
            SELECT dc.id as assignment_id, dc.media_id, dc.display_duration, dc.play_order,
                   m.filename, m.original_name, m.file_type
            FROM device_content dc
            JOIN media m ON dc.media_id = m.id
            WHERE dc.device_id = ? AND dc.is_active = 1
            ORDER BY dc.play_order ASC, dc.created_at ASC
        ''', (device_id,))
        
        content = []
        for row in cursor.fetchall():
            content.append({
                'assignment_id': row[0],
                'media_id': row[1],
                'display_duration': row[2],
                'play_order': row[3] or 0,
                'filename': row[4],
                'original_name': row[5],
                'file_type': row[6]
            })
        
        conn.close()
        return jsonify(content)
    
    except Exception as e:
        logger.error(f"Error getting device content: {e}")
        return jsonify({'error': 'Failed to get device content'}), 500

# Assign content with play order support (UPDATED)
@app.route('/api/assign-content', methods=['POST'])
def assign_content():
    try:
        data = request.get_json()
        device_id = data.get('device_id')
        media_id = data.get('media_id')
        duration = data.get('display_duration', 10)
        
        if not device_id or not media_id:
            return jsonify({'error': 'Device ID and Media ID required'}), 400
        
        conn = sqlite3.connect('signage.db')
        
        # Check if assignment already exists
        cursor = conn.execute('''
            SELECT id FROM device_content 
            WHERE device_id = ? AND media_id = ? AND is_active = 1
        ''', (device_id, media_id))
        
        if cursor.fetchone():
            conn.close()
            return jsonify({'error': 'Content already assigned to this device'}), 400
        
        # Get next play order
        cursor = conn.execute('''
            SELECT COALESCE(MAX(play_order), 0) + 1 
            FROM device_content 
            WHERE device_id = ? AND is_active = 1
        ''', (device_id,))
        next_order = cursor.fetchone()[0]
        
        # Create new assignment
        conn.execute('''
            INSERT INTO device_content (device_id, media_id, display_duration, play_order, is_active)
            VALUES (?, ?, ?, ?, 1)
        ''', (device_id, media_id, duration, next_order))
        
        conn.commit()
        update_content_timestamp()
        conn.close()
        
        logger.info(f"Content {media_id} assigned to device {device_id} with order {next_order}")
        return jsonify({'success': 'Content assigned successfully'})
    
    except Exception as e:
        logger.error(f"Error assigning content: {e}")
        return jsonify({'error': 'Failed to assign content'}), 500

# Update device content settings
@app.route('/api/device-content/<int:assignment_id>', methods=['PUT'])
def update_device_content(assignment_id):
    try:
        data = request.get_json()
        display_duration = data.get('display_duration')
        
        conn = sqlite3.connect('signage.db')
        conn.execute('''
            UPDATE device_content 
            SET display_duration = ? 
            WHERE id = ?
        ''', (display_duration, assignment_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Device content assignment {assignment_id} updated")
        return jsonify({'success': 'Content updated successfully'})
    
    except Exception as e:
        logger.error(f"Error updating device content: {e}")
        return jsonify({'error': 'Failed to update content'}), 500

# Reorder device content
@app.route('/api/device/reorder-content', methods=['PUT'])
def reorder_device_content():
    try:
        data = request.get_json()
        device_id = data.get('device_id')
        content_order = data.get('content_order')  # List of {assignment_id, play_order}
        
        conn = sqlite3.connect('signage.db')
        
        # Update play orders
        for item in content_order:
            conn.execute('''
                UPDATE device_content 
                SET play_order = ? 
                WHERE id = ? AND device_id = ?
            ''', (item['play_order'], item['assignment_id'], device_id))
        
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

# Update device information
@app.route('/api/device/<device_id>', methods=['PUT'])
def update_device(device_id):
    try:
        data = request.get_json()
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
        
# Android API - Device-specific playlists
@app.route('/api/playlist/<device_id>')
def get_playlist(device_id):
    try:
        # Register device checkin - PRESERVE EXISTING CUSTOM NAMES
        conn = sqlite3.connect('signage.db')
        
        # Check if device already exists
        cursor = conn.execute('SELECT custom_name, location FROM devices WHERE device_id = ?', (device_id,))
        existing_device = cursor.fetchone()
        
        if existing_device:
            # Device exists - only update checkin time, status, and IP
            conn.execute('''
                UPDATE devices 
                SET last_checkin = ?, is_active = 1, ip_address = ?
                WHERE device_id = ?
            ''', (datetime.now(), request.remote_addr, device_id))
        else:
            # New device - create with default name
            conn.execute('''
                INSERT INTO devices (device_id, device_name, last_checkin, is_active, ip_address)
                VALUES (?, ?, ?, ?, ?)
            ''', (device_id, f'TV-{device_id[:8]}', datetime.now(), 1, request.remote_addr))
        
        conn.commit()
        
        # Get current day and time
        now = datetime.now()
        today = now.date()
        current_time = now.time()
        current_day = today.strftime('%a').lower()
        
        # Query device-specific content
        cursor = conn.execute('''
            SELECT dc.media_id, m.filename, m.file_type, dc.display_duration,
                   dc.days_of_week, dc.start_date, dc.end_date, dc.start_time, dc.end_time, dc.play_order
            FROM device_content dc
            JOIN media m ON dc.media_id = m.id
            WHERE dc.device_id = ? AND dc.is_active = 1
            AND (dc.start_date IS NULL OR dc.start_date <= ?)
            AND (dc.end_date IS NULL OR dc.end_date >= ?)
            ORDER BY dc.play_order, dc.created_at
        ''', (device_id, today, today))
        
        playlist = []
        for row in cursor.fetchall():
            media_id, filename, file_type, duration, days_json, start_date, end_date, start_time_str, end_time_str, play_order = row
            
            # Check day of week
            days_of_week = json.loads(days_json) if days_json else ['all']
            day_matches = (
                'all' in days_of_week or
                current_day in days_of_week or
                (current_day in ['mon', 'tue', 'wed', 'thu', 'fri'] and 'weekdays' in days_of_week) or
                (current_day in ['sat', 'sun'] and 'weekends' in days_of_week)
            )
            
            # Check time of day if specified
            time_matches = True
            if start_time_str and end_time_str:
                from datetime import time
                start_time = time.fromisoformat(start_time_str)
                end_time = time.fromisoformat(end_time_str)
                time_matches = start_time <= current_time <= end_time
            
            if day_matches and time_matches:
                playlist.append({
                    'id': media_id,
                    'filename': filename,
                    'file_type': file_type,
                    'display_duration': duration,
                    'play_order': play_order,
                    'url': f'http://{SERVER_IP}:5000/uploads/{filename}'
                })
        
        conn.close()
        
        return jsonify({
            'device_id': device_id,
            'server_ip': SERVER_IP,
            'updated_at': now.isoformat(),
            'playlist': playlist
        })
    
    except Exception as e:
        logger.error(f"Error serving device playlist: {e}")
        return jsonify({'error': 'Failed to get playlist'}), 500

# File serving
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    try:
        from flask import send_from_directory
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except Exception as e:
        logger.error(f"File serve error: {e}")
        return "File not found", 404

# Auto refresh
@app.route('/api/system/last-update')
def get_last_update():
    """Return the timestamp of the last content update"""
    try:
        return jsonify({
            'last_update': LAST_CONTENT_UPDATE,
            'server_time': time.time()
        })
    except Exception as e:
        logger.error(f"Error getting last update: {e}")
        return jsonify({'error': 'Failed to get update timestamp'}), 500
        
# System status
@app.route('/api/system/status')
def system_status():
    try:
        conn = sqlite3.connect('signage.db')
        
        cursor = conn.execute('SELECT COUNT(*) FROM devices WHERE is_active = 1')
        active_devices = cursor.fetchone()[0]
        
        cursor = conn.execute('SELECT COUNT(*) FROM media')
        total_media = cursor.fetchone()[0]
        
        # Get storage info
        total_size = 0
        if os.path.exists('uploads'):
            for filename in os.listdir('uploads'):
                filepath = os.path.join('uploads', filename)
                if os.path.isfile(filepath):
                    total_size += os.path.getsize(filepath)
        
        conn.close()
        
        return jsonify({
            'server_ip': SERVER_IP,
            'status': 'running',
            'active_devices': active_devices,
            'total_media': total_media,
            'storage_used_mb': round(total_size / 1024 / 1024, 2)
        })
    
    except Exception as e:
        logger.error(f"System status error: {e}")
        return jsonify({'error': 'Failed to get status'}), 500

# FIXED: Get media info from media table (not device_content)
@app.route('/api/media/<int:media_id>')
def get_media_info(media_id):
    """Get information about a specific media item"""
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

if __name__ == '__main__':
    init_db()
    print(f"🚀 Digital Signage Server starting on: {SERVER_IP}:5000")
    print(f"📱 Android TVs connect to: http://{SERVER_IP}:5000")
    print(f"🌐 Upload from any PC: http://{SERVER_IP}:5000")
    
    # Use Waitress for production
    serve(app, host='0.0.0.0', port=5000, threads=4)