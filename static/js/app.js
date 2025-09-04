// Digital Signage Manager - Main JavaScript File

let currentVideoElement = null;
let currentDevices = [];

// Initialize application
document.addEventListener('DOMContentLoaded', function() {
    // Set default start date to today
    document.getElementById('startDate').valueAsDate = new Date();

    // Initialize time selectors and load devices
    initializeTimeSelectors();
    loadDevicesForAssignment();

    // File input handler
    document.getElementById('file').addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            displayFileInfo(file);
        } else {
            document.getElementById('fileInfo').style.display = 'none';
        }
    });

    // Upload form handler
    document.getElementById('uploadForm').addEventListener('submit', handleUploadSubmit);

    // Load media library on page load
    loadMediaList();
});

// Initialize time selectors with 15-minute increments
function initializeTimeSelectors() {
    const timeSelectors = ['startTime', 'endTime', 'editStartTime', 'editEndTime'];
    
    timeSelectors.forEach(selectorId => {
        const selector = document.getElementById(selectorId);
        if (selector && selector.options.length <= 1) {
            for (let hour = 0; hour < 24; hour++) {
                for (let min = 0; min < 60; min += 15) {
                    const timeStr = `${hour.toString().padStart(2, '0')}:${min.toString().padStart(2, '0')}`;
                    const displayStr = `${hour === 0 ? 12 : hour > 12 ? hour - 12 : hour}:${min.toString().padStart(2, '0')} ${hour < 12 ? 'AM' : 'PM'}`;
                    const option = document.createElement('option');
                    option.value = timeStr;
                    option.textContent = displayStr;
                    selector.appendChild(option);
                }
            }
        }
    });
}

// Handle "All Devices" checkbox behavior
function handleAllDevicesChange() {
    const allDevicesCheckbox = document.getElementById('allDevices');
    const libraryOnlyCheckbox = document.getElementById('libraryOnly');
    const deviceCheckboxes = document.querySelectorAll('#deviceCheckboxes input[type="checkbox"]');
    
    if (allDevicesCheckbox.checked) {
        // Uncheck library only
        libraryOnlyCheckbox.checked = false;
        
        // Check all individual device checkboxes
        deviceCheckboxes.forEach(checkbox => {
            checkbox.checked = true;
        });
    } else {
        // Uncheck all individual device checkboxes
        deviceCheckboxes.forEach(checkbox => {
            checkbox.checked = false;
        });
        
        // Check library only by default
        libraryOnlyCheckbox.checked = true;
    }
}

// Handle individual device checkbox changes
function handleDeviceCheckboxChange() {
    const allDevicesCheckbox = document.getElementById('allDevices');
    const libraryOnlyCheckbox = document.getElementById('libraryOnly');
    const deviceCheckboxes = document.querySelectorAll('#deviceCheckboxes input[type="checkbox"]');
    const checkedDevices = document.querySelectorAll('#deviceCheckboxes input[type="checkbox"]:checked');
    
    // If any device is checked, uncheck library only
    if (checkedDevices.length > 0) {
        libraryOnlyCheckbox.checked = false;
    } else {
        // If no devices checked, check library only
        libraryOnlyCheckbox.checked = true;
    }
    
    // If all devices are checked, check "All Devices"
    if (checkedDevices.length === deviceCheckboxes.length && deviceCheckboxes.length > 0) {
        allDevicesCheckbox.checked = true;
    } else {
        // If not all devices are checked, uncheck "All Devices"
        allDevicesCheckbox.checked = false;
    }
}

// Display file information
function displayFileInfo(file) {
    const fileInfo = document.getElementById('fileInfo');
    const fileName = document.getElementById('fileName');
    const fileSize = document.getElementById('fileSize');
    const fileType = document.getElementById('fileType');
    const videoInfo = document.getElementById('videoInfo');
    const videoMinDuration = document.getElementById('videoMinDuration');

    fileName.textContent = file.name;
    fileSize.textContent = formatFileSize(file.size);
    
    const isVideo = file.type.startsWith('video/');
    fileType.textContent = isVideo ? 'Video' : 'Image';

    if (isVideo) {
        videoInfo.style.display = 'block';
        videoMinDuration.style.display = 'block';
        loadVideoMetadata(file);
    } else {
        videoInfo.style.display = 'none';
        videoMinDuration.style.display = 'none';
        document.getElementById('displayDuration').value = '10';
    }

    fileInfo.style.display = 'block';
}

// Load video metadata
function loadVideoMetadata(file) {
    if (currentVideoElement) {
        currentVideoElement.remove();
    }

    currentVideoElement = document.createElement('video');
    currentVideoElement.preload = 'metadata';
    
    currentVideoElement.onloadedmetadata = function() {
        const duration = Math.ceil(currentVideoElement.duration);
        const resolution = `${currentVideoElement.videoWidth}x${currentVideoElement.videoHeight}`;
        
        document.getElementById('videoDuration').textContent = formatDuration(duration);
        document.getElementById('videoResolution').textContent = resolution;
        document.getElementById('videoLength').textContent = `${duration}s`;
        
        // Update duration selector to show minimum for video
        const durationSelect = document.getElementById('displayDuration');
        const options = durationSelect.options;
        for (let i = 0; i < options.length; i++) {
            const value = parseInt(options[i].value);
            if (value < duration) {
                options[i].disabled = true;
                options[i].textContent += ' (too short)';
            } else {
                options[i].disabled = false;
                options[i].textContent = options[i].textContent.replace(' (too short)', '');
            }
        }
        
        // Set minimum valid duration
        if (parseInt(durationSelect.value) < duration) {
            for (let i = 0; i < options.length; i++) {
                if (parseInt(options[i].value) >= duration) {
                    durationSelect.selectedIndex = i;
                    break;
                }
            }
        }
    };

    currentVideoElement.src = URL.createObjectURL(file);
}

// Format file size
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Format duration
function formatDuration(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// Calculate end date based on duration
function calculateEndDate() {
    const startDate = document.getElementById('startDate').value;
    const rangeValue = document.getElementById('dateRange').value;
    const endDateInput = document.getElementById('endDate');
    
    if (rangeValue === 'custom') {
        endDateInput.readOnly = false;
        endDateInput.style.backgroundColor = '';
        return;
    }
    
    endDateInput.readOnly = true;
    endDateInput.style.backgroundColor = '#f8f9fa';
    
    if (startDate && rangeValue && rangeValue !== 'custom') {
        const start = new Date(startDate);
        const end = new Date(start.getFullYear(), start.getMonth() + parseInt(rangeValue), start.getDate());
        endDateInput.value = end.toISOString().split('T')[0];
    } else {
        endDateInput.value = '';
    }
}

// Load devices for assignment
async function loadDevicesForAssignment() {
    try {
        const response = await fetch('/api/devices');
        currentDevices = await response.json();
        
        // Update the old dropdown (still used in modal)
        const assignDeviceSelect = document.getElementById('assignDeviceSelect');
        if (assignDeviceSelect) {
            currentDevices.forEach(device => {
                const option = document.createElement('option');
                option.value = device.device_id;
                option.textContent = device.display_name;
                assignDeviceSelect.appendChild(option);
            });
        }
        
        // Update the device checkboxes
        updateDeviceCheckboxes();
        
    } catch (error) {
        console.error('Error loading devices:', error);
        document.getElementById('deviceCheckboxes').innerHTML = '<div class="text-danger small">Error loading devices</div>';
    }
}

// Update device checkboxes
function updateDeviceCheckboxes() {
    const container = document.getElementById('deviceCheckboxes');
    
    if (currentDevices.length === 0) {
        container.innerHTML = '<div class="text-muted small">No devices found</div>';
        return;
    }
    
    let html = '';
    currentDevices.forEach(device => {
        const deviceName = device.display_name || device.device_name;
        html += `
            <div class="form-check form-check-sm mb-1">
                <input class="form-check-input device-checkbox" type="checkbox" 
                       id="device_${device.device_id}" value="${device.device_id}"
                       onchange="handleDeviceCheckboxChange()">
                <label class="form-check-label" for="device_${device.device_id}">
                    ${deviceName}
                </label>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

// Handle upload form submission
async function handleUploadSubmit(e) {
    e.preventDefault();
    
    const formData = new FormData();
    const fileInput = document.getElementById('file');
    const file = fileInput.files[0];
    
    if (!file) {
        alert('Please select a file');
        return;
    }

    formData.append('file', file);
    
    // Collect selected days
    const selectedDays = [];
    document.querySelectorAll('input[type="checkbox"][id^="day"]:checked').forEach(cb => {
        selectedDays.push(cb.value);
    });
    
    // If no days selected, default to all days
    const daysToUse = selectedDays.length > 0 ? selectedDays : ['all'];
    
    // Get video duration if it's a video file
    let videoDuration = null;
    if (currentVideoElement && currentVideoElement.duration) {
        videoDuration = Math.ceil(currentVideoElement.duration);
    }
    
    // Handle device assignment based on checkboxes
    let deviceAssignment = null;
    const libraryOnly = document.getElementById('libraryOnly').checked;
    const allDevices = document.getElementById('allDevices').checked;
    
    if (!libraryOnly) {
        if (allDevices) {
            deviceAssignment = 'all';
        } else {
            // Get individual selected devices
            const selectedDevices = [];
            document.querySelectorAll('#deviceCheckboxes input[type="checkbox"]:checked').forEach(cb => {
                selectedDevices.push(cb.value);
            });
            
            if (selectedDevices.length > 0) {
                // For now, we'll use the first selected device
                // Later you might want to modify the backend to handle multiple devices
                deviceAssignment = selectedDevices[0];
            }
        }
    }
    
    // Get time values
    const startTime = document.getElementById('startTime').value || null;
    const endTime = document.getElementById('endTime').value || null;
    
    const schedulingData = {
        days_of_week: daysToUse,
        display_duration: parseInt(document.getElementById('displayDuration').value),
        video_duration: videoDuration,
        start_time: startTime,
        end_time: endTime,
        start_date: document.getElementById('startDate').value || null,
        end_date: document.getElementById('endDate').value || null,
        device_assignment: deviceAssignment
    };
    
    formData.append('scheduling', JSON.stringify(schedulingData));
    
    try {
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (response.ok) {
            alert('Content uploaded successfully!');
            resetForm();
            loadMediaList();
        } else {
            alert('Error: ' + result.error);
        }
    } catch (error) {
        alert('Upload failed: ' + error.message);
    }
}

// Reset form to default state
function resetForm() {
    document.getElementById('uploadForm').reset();
    document.getElementById('fileInfo').style.display = 'none';
    document.getElementById('startDate').valueAsDate = new Date();
    
    // Reset device assignment to defaults
    document.getElementById('libraryOnly').checked = true;
    document.getElementById('allDevices').checked = false;
    document.querySelectorAll('#deviceCheckboxes input[type="checkbox"]').forEach(cb => {
        cb.checked = false;
    });
    
    // Reset all day checkboxes to checked
    document.querySelectorAll('input[type="checkbox"][id^="day"]').forEach(cb => {
        cb.checked = true;
    });
}

// Get media status
function getMediaStatus(media) {
    const now = new Date();
    const startDate = media.start_date ? new Date(media.start_date) : null;
    const endDate = media.end_date ? new Date(media.end_date) : null;
    
    if (!media.is_active) {
        return { status: 'paused', icon: 'fas fa-pause-circle', class: 'status-paused', text: 'Paused' };
    }
    
    if (endDate && now > endDate) {
        return { status: 'expired', icon: 'fas fa-times-circle', class: 'status-expired', text: 'Expired' };
    }
    
    if (startDate && now < startDate) {
        return { status: 'scheduled', icon: 'fas fa-clock', class: 'status-scheduled', text: 'Scheduled' };
    }
    
    return { status: 'active', icon: 'fas fa-play-circle', class: 'status-active', text: 'Active' };
}

// Create thumbnail
function createThumbnail(media) {
    if (media.file_type === 'image') {
        return `<img src="/uploads/${media.filename}" class="media-thumbnail" alt="Thumbnail">`;
    } else {
        return `<div class="thumbnail-placeholder"><i class="fas fa-video"></i></div>`;
    }
}

// Format schedule details
function formatScheduleDetails(media) {
    let details = '';
    
    // Display duration
    details += `<span class="detail-badge"><i class="fas fa-clock"></i> ${media.display_duration || 10}s</span>`;
    
    // Time range
    if (media.start_time || media.end_time) {
        const timeRange = `${media.start_time || '00:00'}-${media.end_time || '23:59'}`;
        details += `<span class="detail-badge"><i class="fas fa-clock"></i> ${timeRange}</span>`;
    }
    
    // Date range
    if (media.start_date || media.end_date) {
        const startDate = media.start_date ? new Date(media.start_date).toLocaleDateString('en-US', {month: 'short', day: 'numeric'}) : 'No start';
        const endDate = media.end_date ? new Date(media.end_date).toLocaleDateString('en-US', {month: 'short', day: 'numeric'}) : 'No end';
        details += `<span class="detail-badge"><i class="fas fa-calendar"></i> ${startDate} - ${endDate}</span>`;
    }
    
    return details;
}

// Format days of week
function formatDaysOfWeek(daysJson) {
    if (!daysJson) return '<span class="day-tag">All days</span>';
    
    try {
        const days = JSON.parse(daysJson);
        if (days.includes('all')) return '<span class="day-tag">All days</span>';
        if (days.includes('weekdays')) return '<span class="day-tag">Weekdays</span>';
        if (days.includes('weekends')) return '<span class="day-tag">Weekends</span>';
        
        return days.map(day => `<span class="day-tag">${day.toUpperCase()}</span>`).join('');
    } catch {
        return '<span class="day-tag">All days</span>';
    }
}

// Toggle media status
async function toggleMediaStatus(mediaId, currentStatus) {
    try {
        const response = await fetch(`/api/media/${mediaId}/toggle`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ is_active: !currentStatus })
        });
        
        if (response.ok) {
            loadMediaList();
        } else {
            alert('Failed to update media status');
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

// Delete media
async function deleteMedia(mediaId, filename) {
    if (!confirm(`Delete "${filename}"? This will remove it from all devices and cannot be undone.`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/media/${mediaId}`, { method: 'DELETE' });
        
        if (response.ok) {
            loadMediaList();
        } else {
            alert('Failed to delete media');
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

// Edit media
function editMedia(mediaId) {
    document.getElementById('editMediaId').value = mediaId;
    new bootstrap.Modal(document.getElementById('editMediaModal')).show();
}

// Save media edit
async function saveMediaEdit() {
    const mediaId = document.getElementById('editMediaId').value;
    
    // Collect selected days
    const selectedDays = [];
    document.querySelectorAll('input[type="checkbox"][id^="editDay"]:checked').forEach(cb => {
        selectedDays.push(cb.value);
    });
    
    // If no days selected, default to all days
    const daysToUse = selectedDays.length > 0 ? selectedDays : ['all'];
    
    // Get time values
    const startTime = document.getElementById('editStartTime').value || null;
    const endTime = document.getElementById('editEndTime').value || null;
    
    const updateData = {
        days_of_week: daysToUse,
        display_duration: parseInt(document.getElementById('editDisplayDuration').value),
        start_time: startTime,
        end_time: endTime,
        start_date: document.getElementById('editStartDate').value || null,
        end_date: document.getElementById('editEndDate').value || null
    };
    
    try {
        const response = await fetch(`/api/media/${mediaId}/schedule`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updateData)
        });
        
        if (response.ok) {
            bootstrap.Modal.getInstance(document.getElementById('editMediaModal')).hide();
            loadMediaList();
        } else {
            alert('Failed to save changes');
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

// Show device assignment modal
function showDeviceAssignment(mediaId) {
    document.getElementById('assignMediaId').value = mediaId;
    new bootstrap.Modal(document.getElementById('deviceAssignModal')).show();
}

// Assign to device
async function assignToDevice() {
    const mediaId = document.getElementById('assignMediaId').value;
    const deviceId = document.getElementById('assignDeviceSelect').value;
    const duration = document.getElementById('assignDuration').value;
    
    if (!deviceId) {
        alert('Please select a device');
        return;
    }
    
    try {
        let response;
        if (deviceId === 'all') {
            response = await fetch('/api/assign-all-devices', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    media_id: parseInt(mediaId),
                    display_duration: parseInt(duration)
                })
            });
        } else {
            response = await fetch('/api/assign-content', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    device_id: deviceId,
                    media_id: parseInt(mediaId),
                    display_duration: parseInt(duration)
                })
            });
        }
        
        const result = await response.json();
        
        if (response.ok) {
            bootstrap.Modal.getInstance(document.getElementById('deviceAssignModal')).hide();
            loadMediaList();
        } else {
            alert('Error: ' + result.error);
        }
    } catch (error) {
        alert('Assignment failed: ' + error.message);
    }
}

// Load media library
async function loadMediaList() {
    try {
        const response = await fetch('/api/media/detailed');
        const mediaList = await response.json();
        const container = document.getElementById('mediaList');
        
        if (mediaList.length === 0) {
            container.innerHTML = '<p class="text-muted text-center">No media uploaded yet.</p>';
            return;
        }
        
        let html = '';
        
        mediaList.forEach(media => {
            const status = getMediaStatus(media);
            const fileSize = Math.round(media.file_size / 1024) + ' KB';
            const uploadDate = new Date(media.created_at).toLocaleDateString();
            const thumbnail = createThumbnail(media);
            const scheduleDetails = formatScheduleDetails(media);
            const daysDisplay = formatDaysOfWeek(media.days_of_week);
            
            html += `
                <div class="media-item">
                    <div class="row align-items-start">
                        <div class="col-auto">
                            ${thumbnail}
                        </div>
                        <div class="col">
                            <div class="d-flex align-items-center mb-1">
                                <i class="${status.icon} status-icon ${status.class}" title="${status.text}"></i>
                                <strong>${media.original_name}</strong>
                            </div>
                            <div class="small text-muted mb-2">
                                ${media.file_type} • ${fileSize} • ${uploadDate}
                            </div>
                            <div class="day-tags mb-2">
                                ${daysDisplay}
                            </div>
                            <div class="media-details">
                                ${scheduleDetails}
                            </div>
                        </div>
                        <div class="col-auto">
                            <button class="btn btn-info btn-sm devices-popup me-2" onclick="showDeviceAssignment(${media.id})" 
                                    title="Assign to devices">
                                <i class="fas fa-tv"></i> ${media.assignment_count}
                            </button>
                        </div>
                        <div class="col-auto">
                            <div class="form-check form-switch">
                                <input class="form-check-input" type="checkbox" ${media.is_active ? 'checked' : ''} 
                                       onchange="toggleMediaStatus(${media.id}, ${media.is_active})" title="Active/Inactive">
                            </div>
                        </div>
                        <div class="col-auto">
                            <button class="btn btn-outline-secondary btn-sm me-2" onclick="editMedia(${media.id})" title="Edit">
                                <i class="fas fa-edit"></i>
                            </button>
                            <button class="btn btn-outline-danger btn-sm" onclick="deleteMedia(${media.id}, '${media.original_name}')" title="Delete">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </div>
                </div>
            `;
        });
        
        container.innerHTML = html;
        
    } catch (error) {
        document.getElementById('mediaList').innerHTML = '<p class="text-danger">Error loading media library.</p>';
    }
}
# Add these routes to your production_app.py file

# Device Management Page Route
@app.route('/devices')
def device_management():
    return render_template('devices.html', server_ip=SERVER_IP)

# Update device content assignment with play order
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
        conn.close()
        
        logger.info(f"Content reordered for device {device_id}")
        return jsonify({'success': 'Content reordered successfully'})
    
    except Exception as e:
        logger.error(f"Error reordering content: {e}")
        return jsonify({'error': 'Failed to reorder content'}), 500

# Get device content with play order
@app.route('/api/device/<device_id>/content')
def get_device_content_ordered(device_id):
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

# Update the assign_content function to set initial play order
@app.route('/api/assign-content', methods=['POST'])
def assign_content_with_order():
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
        conn.close()
        
        logger.info(f"Content {media_id} assigned to device {device_id} with order {next_order}")
        return jsonify({'success': 'Content assigned successfully'})
    
    except Exception as e:
        logger.error(f"Error assigning content: {e}")
        return jsonify({'error': 'Failed to assign content'}), 500