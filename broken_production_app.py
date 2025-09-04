"""
@app_main
Digital Signage Content Management System
Refactored following DRY and SOLID principles for maintainability
"""

# Standard library imports
import os
import json
import socket
import logging
import sqlite3
from datetime import datetime, date, time
from typing import Dict, List, Optional, Tuple, Union

# Third-party imports
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
from waitress import serve

# =============================================================================
# @configuration - Application Configuration Class
# =============================================================================
class AppConfig:
    """Centralized application configuration following Single Responsibility"""
    
    SECRET_KEY = 'your-secret-key-change-this-in-production'
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi', 'webm', 'mkv'}
    LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
    
    @staticmethod
    def get_server_ip() -> str:
        """@network_utils - Get server IP automatically"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "localhost"

# =============================================================================
# @database_manager - Database Operations Handler
# =============================================================================
class DatabaseManager:
    """Handles all database operations following Single Responsibility Principle"""
    
    DB_NAME = 'signage.db'
    
    @classmethod
    def get_connection(cls) -> sqlite3.Connection:
        """@db_connection - Get database connection"""
        return sqlite3.connect(cls.DB_NAME)
    
    @classmethod
    def init_database(cls) -> None:
        """@db_init - Initialize database with all required tables"""
        conn = cls.get_connection()
        
        # Media table schema
        conn.execute('''
            CREATE TABLE IF NOT EXISTS media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                original_name TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_size INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                uploaded_from_ip TEXT
            )
        ''')
        
        # Devices table schema
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
        
        # Device content assignments schema
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
        
        # Analytics table schema
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
        
        # Handle schema upgrades gracefully
        try:
            conn.execute('ALTER TABLE device_content ADD COLUMN video_duration INTEGER')
        except sqlite3.OperationalError:
            pass  # Column already exists
            
        conn.commit()
        conn.close()
        logging.info("Database initialized successfully")

# =============================================================================
# @file_manager - File Operations Handler
# =============================================================================
class FileManager:
    """Handles file upload, validation, and storage operations"""
    
    def __init__(self, upload_folder: str, allowed_extensions: set):
        self.upload_folder = upload_folder
        self.allowed_extensions = allowed_extensions
        self._ensure_directories()
    
    def _ensure_directories(self) -> None:
        """@directory_setup - Ensure required directories exist"""
        os.makedirs(self.upload_folder, exist_ok=True)
        os.makedirs('logs', exist_ok=True)
    
    def is_allowed_file(self, filename: str) -> bool:
        """@file_validation - Check if file extension is allowed"""
        return ('.' in filename and 
                filename.rsplit('.', 1)[1].lower() in self.allowed_extensions)
    
    def save_uploaded_file(self, file, remote_addr: str) -> Tuple[str, int, str]:
        """@file_upload - Save uploaded file and return details"""
        if not file or file.filename == '' or not self.is_allowed_file(file.filename):
            raise ValueError("Invalid file or file type")
        
        # Generate unique filename
        original_filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
        unique_filename = timestamp + original_filename
        file_path = os.path.join(self.upload_folder, unique_filename)
        
        try:
            file.save(file_path)
        except Exception as e:
            logging.error(f"File save error: {e}")
            raise RuntimeError("Failed to save file to disk")
        
        file_size = os.path.getsize(file_path)
        file_type = self._determine_file_type(original_filename)
        
        return unique_filename, file_size, file_type
    
    def _determine_file_type(self, filename: str) -> str:
        """@file_type_detection - Determine if file is image or video"""
        return ('image' if filename.lower().endswith(('png', 'jpg', 'jpeg', 'gif')) 
                else 'video')
    
    def delete_file(self, filename: str) -> bool:
        """@file_deletion - Delete physical file from storage"""
        file_path = os.path.join(self.upload_folder, filename)
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
        except Exception as e:
            logging.error(f"File deletion error: {e}")
        return False

# =============================================================================
# @media_service - Media Business Logic
# =============================================================================
class MediaService:
    """Handles media-related business logic operations"""
    
    def __init__(self):
        self.db = DatabaseManager()
    
    def create_media_record(self, filename: str, original_name: str, 
                          file_type: str, file_size: int, ip_address: str) -> int:
        """@media_creation - Create new media record in database"""
        conn = self.db.get_connection()
        cursor = conn.execute('''
            INSERT INTO media (filename, original_name, file_type, file_size, uploaded_from_ip)
            VALUES (?, ?, ?, ?, ?)
        ''', (filename, original_name, file_type, file_size, ip_address))
        
        media_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return media_id
    
    def get_media_list(self, detailed: bool = False) -> List[Dict]:
        """@media_retrieval - Get list of media with optional detailed information"""
        conn = self.db.get_connection()
        
        if detailed:
            query = '''
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
            '''
        else:
            query = '''
                SELECT m.id, m.filename, m.original_name, m.file_type, m.file_size, m.created_at,
                       (SELECT COUNT(*) FROM device_content WHERE media_id = m.id AND is_active = 1) as assignment_count,
                       (SELECT MIN(start_date) FROM device_content WHERE media_id = m.id) as start_date,
                       (SELECT MAX(end_date) FROM device_content WHERE media_id = m.id) as end_date,
                       (SELECT MIN(is_active) FROM device_content WHERE media_id = m.id) as is_active
                FROM media m
                ORDER BY m.created_at DESC
            '''
        
        cursor = conn.execute(query)
        media_list = []
        
        for row in cursor.fetchall():
            media_dict = {
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
            }
            
            if detailed and len(row) > 10:
                media_dict.update({
                    'display_duration': row[10],
                    'start_time': row[11],
                    'end_time': row[12],
                    'days_of_week': row[13]
                })
            
            media_list.append(media_dict)
        
        conn.close()
        return media_list
    
    def delete_media(self, media_id: int, file_manager: FileManager) -> bool:
        """@media_deletion - Delete media and all associated records"""
        conn = self.db.get_connection()
        
        # Get filename for physical file deletion
        cursor = conn.execute('SELECT filename FROM media WHERE id = ?', (media_id,))
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            return False
        
        filename = result[0]
        
        # Delete associated records
        conn.execute('DELETE FROM device_content WHERE media_id = ?', (media_id,))
        conn.execute('DELETE FROM playback_analytics WHERE media_id = ?', (media_id,))
        conn.execute('DELETE FROM media WHERE id = ?', (media_id,))
        
        conn.commit()
        conn.close()
        
        # Delete physical file
        file_manager.delete_file(filename)
        logging.info(f"Media {media_id} ({filename}) deleted successfully")
        return True

# =============================================================================
# @schedule_service - Scheduling Operations
# =============================================================================
class ScheduleService:
    """Handles content scheduling and device assignment operations"""
    
    def __init__(self):
        self.db = DatabaseManager()
    
    def create_device_assignment(self, device_id: str, media_id: int, 
                               schedule_data: Dict) -> None:
        """@device_assignment - Create device content assignment"""
        conn = self.db.get_connection()
        
        days_json = json.dumps(schedule_data.get('days_of_week', ['all']))
        display_duration = schedule_data.get('display_duration', 10)
        video_duration = schedule_data.get('video_duration')
        
        conn.execute('''
            INSERT INTO device_content 
            (device_id, media_id, display_duration, video_duration, days_of_week, 
             start_date, end_date, start_time, end_time, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        ''', (
            device_id, media_id, display_duration, video_duration, days_json,
            schedule_data.get('start_date'), schedule_data.get('end_date'),
            schedule_data.get('start_time'), schedule_data.get('end_time')
        ))
        
        conn.commit()
        conn.close()
    
    def update_media_schedule(self, media_id: int, schedule_data: Dict) -> bool:
        """@update_media_schedule - Update scheduling for existing media"""
        conn = self.db.get_connection()
        
        days_list = schedule_data.get('days_of_week', [])
        if not days_list:
            days_list = ['all']
        days_json = json.dumps(days_list)
        
        conn.execute('''
            UPDATE device_content 
            SET days_of_week = ?, display_duration = ?, start_time = ?, end_time = ?, 
                start_date = ?, end_date = ?
            WHERE media_id = ?
        ''', (
            days_json,
            schedule_data.get('display_duration', 10),
            schedule_data.get('start_time'),
            schedule_data.get('end_time'),
            schedule_data.get('start_date'),
            schedule_data.get('end_date'),
            media_id
        ))
        
        conn.commit()
        conn.close()
        logging.info(f"Media {media_id} schedule updated")
        return True

# =============================================================================
# @device_service - Device Management
# =============================================================================
class DeviceService:
    """Handles device registration, updates, and playlist generation"""
    
    def __init__(self):
        self.db = DatabaseManager()
    
    def register_device_checkin(self, device_id: str, ip_address: str) -> None:
        """@device_checkin - Register or update device check-in"""
        conn = self.db.get_connection()
        
        cursor = conn.execute('SELECT custom_name, location FROM devices WHERE device_id = ?', 
                            (device_id,))
        existing_device = cursor.fetchone()
        
        if existing_device:
            # Update existing device
            conn.execute('''
                UPDATE devices 
                SET last_checkin = ?, is_active = 1, ip_address = ?
                WHERE device_id = ?
            ''', (datetime.now(), ip_address, device_id))
        else:
            # Create new device
            conn.execute('''
                INSERT INTO devices (device_id, device_name, last_checkin, is_active, ip_address)
                VALUES (?, ?, ?, ?, ?)
            ''', (device_id, f'TV-{device_id[:8]}', datetime.now(), 1, ip_address))
        
        conn.commit()
        conn.close()
    
    def get_device_playlist(self, device_id: str, server_ip: str) -> Dict:
        """@playlist_generation - Generate device-specific playlist"""
        conn = self.db.get_connection()
        
        now = datetime.now()
        today = now.date()
        current_time = now.time()
        current_day = today.strftime('%a').lower()
        
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
            if self._should_play_content(row, current_day, current_time):
                playlist.append({
                    'id': row[0],
                    'filename': row[1],
                    'file_type': row[2],
                    'display_duration': row[3],
                    'play_order': row[9],
                    'url': f'http://{server_ip}:5000/uploads/{row[1]}'
                })
        
        conn.close()
        
        return {
            'device_id': device_id,
            'server_ip': server_ip,
            'updated_at': now.isoformat(),
            'playlist': playlist
        }
    
    def _should_play_content(self, content_row: tuple, current_day: str, current_time: time) -> bool:
        """@content_filtering - Determine if content should play based on schedule"""
        days_json = content_row[4]
        start_time_str = content_row[7]
        end_time_str = content_row[8]
        
        # Check day of week
        days_of_week = json.loads(days_json) if days_json else ['all']
        day_matches = (
            'all' in days_of_week or
            current_day in days_of_week or
            (current_day in ['mon', 'tue', 'wed', 'thu', 'fri'] and 'weekdays' in days_of_week) or
            (current_day in ['sat', 'sun'] and 'weekends' in days_of_week)
        )
        
        # Check time of day
        time_matches = True
        if start_time_str and end_time_str:
            start_time = time.fromisoformat(start_time_str)
            end_time = time.fromisoformat(end_time_str)
            time_matches = start_time <= current_time <= end_time
        
        return day_matches and time_matches

# =============================================================================
# @flask_app - Main Flask Application
# =============================================================================
def create_app() -> Flask:
    """@app_factory - Create and configure Flask application"""
    app = Flask(__name__)
    
    # Configure app
    app.config['SECRET_KEY'] = AppConfig.SECRET_KEY
    app.config['UPLOAD_FOLDER'] = AppConfig.UPLOAD_FOLDER
    app.config['MAX_CONTENT_LENGTH'] = AppConfig.MAX_CONTENT_LENGTH
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format=AppConfig.LOG_FORMAT,
        handlers=[
            logging.FileHandler(f'logs/signage_{datetime.now().strftime("%Y%m%d")}.log'),
            logging.StreamHandler()
        ]
    )
    
    # Initialize services
    file_manager = FileManager(AppConfig.UPLOAD_FOLDER, AppConfig.ALLOWED_EXTENSIONS)
    media_service = MediaService()
    schedule_service = ScheduleService()
    device_service = DeviceService()
    server_ip = AppConfig.get_server_ip()
    
    # =============================================================================
    # @routes_main - Main Application Routes
    # =============================================================================
    @app.route('/')
    def index():
        return render_template('index.html', server_ip=server_ip)

    @app.route('/devices')
    def device_management():
        return render_template('devices.html', server_ip=server_ip)

    @app.route('/device/<device_id>')
    def device_detail(device_id):
        return render_template('device_detail.html', server_ip=server_ip, device_id=device_id)

    @app.route('/dashboard')
    def dashboard():
        return render_template('dashboard.html', server_ip=server_ip)

    # =============================================================================
    # @routes_upload - File Upload Endpoints
    # =============================================================================
    @app.route('/upload', methods=['POST'])
    def upload_file():
        """@uploads - Handle file upload and scheduling"""
        try:
            if 'file' not in request.files:
                return jsonify({'error': 'No file selected'}), 400
            
            file = request.files['file']
            
            # Save file
            unique_filename, file_size, file_type = file_manager.save_uploaded_file(
                file, request.remote_addr)
            
            # Create media record
            media_id = media_service.create_media_record(
                unique_filename, file.filename, file_type, file_size, request.remote_addr)
            
            # Handle scheduling if provided
            scheduling_data = request.form.get('scheduling')
            if scheduling_data:
                try:
                    schedule = json.loads(scheduling_data)
                    device_assignment = schedule.get('device_assignment')
                    
                    if device_assignment:
                        if device_assignment == 'all':
                            # Assign to all active devices
                            conn = DatabaseManager.get_connection()
                            cursor = conn.execute('SELECT device_id FROM devices WHERE is_active = 1')
                            devices = cursor.fetchall()
                            conn.close()
                            
                            for device in devices:
                                schedule_service.create_device_assignment(
                                    device[0], media_id, schedule)
                        else:
                            # Assign to specific device
                            schedule_service.create_device_assignment(
                                device_assignment, media_id, schedule)
                        
                        logging.info(f"Content {media_id} scheduled successfully")
                
                except json.JSONDecodeError as e:
                    logging.warning(f"Invalid scheduling data: {e}")
            
            return jsonify({'success': 'File uploaded and scheduled successfully'})
        
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        except RuntimeError as e:
            return jsonify({'error': str(e)}), 500
        except Exception as e:
            logging.error(f"Upload error: {e}")
            return jsonify({'error': f'Upload failed: {str(e)}'}), 500

    # =============================================================================
    # @routes_api_media - Media Management API Endpoints
    # =============================================================================
    @app.route('/api/media')
    def get_media_list():
        """@media_list - Get basic media list"""
        try:
            media_list = media_service.get_media_list(detailed=False)
            return jsonify(media_list)
        except Exception as e:
            logging.error(f"Error getting media list: {e}")
            return jsonify({'error': 'Failed to get media list'}), 500

    @app.route('/api/media/detailed')
    def get_detailed_media_list():
        """@media_detailed - Get detailed media list with scheduling info"""
        try:
            media_list = media_service.get_media_list(detailed=True)
            return jsonify(media_list)
        except Exception as e:
            logging.error(f"Error getting detailed media list: {e}")
            return jsonify({'error': 'Failed to get detailed media list'}), 500

    @app.route('/api/media/<int:media_id>/schedule', methods=['PUT'])
    def update_media_schedule(media_id):
        """@update_media_schedule - Update media scheduling"""
        try:
            data = request.get_json()
            success = schedule_service.update_media_schedule(media_id, data)
            
            if success:
                return jsonify({'success': 'Schedule updated successfully'})
            else:
                return jsonify({'error': 'Failed to update schedule'}), 500
                
        except Exception as e:
            logging.error(f"Error updating media schedule: {e}")
            return jsonify({'error': 'Failed to update schedule'}), 500

    @app.route('/api/media/<int:media_id>', methods=['DELETE'])
    def delete_media(media_id):
        """@media_delete - Delete media completely"""
        try:
            success = media_service.delete_media(media_id, file_manager)
            
            if success:
                return jsonify({'success': 'Media deleted successfully'})
            else:
                return jsonify({'error': 'Media not found'}), 404
                
        except Exception as e:
            logging.error(f"Error deleting media: {e}")
            return jsonify({'error': 'Failed to delete media'}), 500

    # =============================================================================
    # @routes_api_devices - Device Management API Endpoints
    # =============================================================================
    @app.route('/api/playlist/<device_id>')
    def get_playlist(device_id):
        """@device_playlist - Get device-specific playlist"""
        try:
            # Register device check-in
            device_service.register_device_checkin(device_id, request.remote_addr)
            
            # Generate and return playlist
            playlist_data = device_service.get_device_playlist(device_id, server_ip)
            return jsonify(playlist_data)
            
        except Exception as e:
            logging.error(f"Error serving device playlist: {e}")
            return jsonify({'error': 'Failed to get playlist'}), 500
    
    
    
    @app.route('/uploads/<filename>')
    def uploaded_file(filename):
        """@file_serve - Serve uploaded files"""
        try:
            from flask import send_from_directory
            return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
        except Exception as e:
            logging.error(f"File serve error: {e}")
            return "File not found", 404
    @app.route('/api/devices')
    def get_devices():
        """@devices_list - Get list of all devices"""
        try:
            conn = DatabaseManager.get_connection()
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
            logging.error(f"Error getting devices: {e}")
            return jsonify({'error': 'Failed to get devices'}), 500

    @app.route('/api/assign-all-devices', methods=['POST'])
    def assign_all_devices():
        """@assign_all - Assign content to all devices"""
        try:
            data = request.get_json()
            media_id = data.get('media_id')
            duration = data.get('display_duration', 10)
            
            if not media_id:
                return jsonify({'error': 'Media ID required'}), 400
            
            conn = DatabaseManager.get_connection()
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
                    conn.execute('''
                        INSERT INTO device_content (device_id, media_id, display_duration, is_active)
                        VALUES (?, ?, ?, 1)
                    ''', (device_id, media_id, duration))
                    assigned_count += 1
            
            conn.commit()
            conn.close()
            
            logging.info(f"Media {media_id} assigned to {assigned_count} devices")
            return jsonify({'success': f'Content assigned to {assigned_count} devices'})
        
        except Exception as e:
            logging.error(f"Error assigning to all devices: {e}")
            return jsonify({'error': 'Failed to assign to all devices'}), 500

    @app.route('/api/assign-content', methods=['POST'])
    def assign_content():
        """@assign_content - Assign content to specific device"""
        try:
            data = request.get_json()
            device_id = data.get('device_id')
            media_id = data.get('media_id')
            duration = data.get('display_duration', 10)
            
            if not device_id or not media_id:
                return jsonify({'error': 'Device ID and Media ID required'}), 400
            
            conn = DatabaseManager.get_connection()
            
            # Check if assignment already exists
            cursor = conn.execute('''
                SELECT id FROM device_content 
                WHERE device_id = ? AND media_id = ? AND is_active = 1
            ''', (device_id, media_id))
            
            if cursor.fetchone():
                conn.close()
                return jsonify({'error': 'Content already assigned to this device'}), 400
            
            conn.execute('''
                INSERT INTO device_content (device_id, media_id, display_duration, is_active)
                VALUES (?, ?, ?, 1)
            ''', (device_id, media_id, duration))
            
            conn.commit()
            conn.close()
            
            logging.info(f"Content {media_id} assigned to device {device_id}")
            return jsonify({'success': 'Content assigned successfully'})
        
        except Exception as e:
            logging.error(f"Error assigning content: {e}")
            return jsonify({'error': 'Failed to assign content'}), 500

    @app.route('/api/media/<int:media_id>/toggle', methods=['PUT'])
    def toggle_media_status(media_id):
        """@media_toggle - Toggle media active/inactive status"""
        try:
            data = request.get_json()
            is_active = data.get('is_active', True)
            
            conn = DatabaseManager.get_connection()
            conn.execute('''
                UPDATE device_content 
                SET is_active = ? 
                WHERE media_id = ?
            ''', (is_active, media_id))
            
            conn.commit()
            conn.close()
            
            logging.info(f"Media {media_id} status changed to {'active' if is_active else 'inactive'}")
            return jsonify({'success': 'Media status updated'})
        
        except Exception as e:
            logging.error(f"Error toggling media status: {e}")
            return jsonify({'error': 'Failed to update media status'}), 500

    return app
    return app

# =============================================================================
# @app_main - Application Entry Point
# =============================================================================
if __name__ == '__main__':
    # Initialize database
    DatabaseManager.init_database()
    
    # Create Flask app
    app = create_app()
    server_ip = AppConfig.get_server_ip()
    
    # Start server
    print(f"🚀 Digital Signage Server starting on: {server_ip}:5000")
    print(f"📱 Android TVs connect to: http://{server_ip}:5000")
    print(f"🌐 Upload from any PC: http://{server_ip}:5000")
    
    serve(app, host='0.0.0.0', port=5000, threads=4)