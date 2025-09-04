/**
 * @upload_handler - File Upload Processing Module
 * Handles form submission, file uploads, and scheduling integration
 */

class UploadHandler {
    constructor() {
        this.form = document.getElementById('uploadForm');
        this.fileManager = null;
        this.deviceList = [];
        this.init();
    }

    /**
     * @upload_init - Initialize upload handler
     */
    init() {
        this.bindEvents();
        this.loadDevices();
    }

    /**
     * @upload_events - Bind upload form events
     */
    bindEvents() {
        if (this.form) {
            this.form.addEventListener('submit', (e) => this.handleFormSubmit(e));
        }
    }

    /**
     * @devices_loading - Load available devices for assignment
     */
    async loadDevices() {
        try {
            const devices = await Utils.apiRequest('/api/devices');
            this.deviceList = devices;
            this.populateDeviceDropdowns();
        } catch (error) {
            console.error('Error loading devices:', error);
            // Continue without device list - not critical for basic upload
        }
    }

    /**
     * @device_dropdown_population - Populate device assignment dropdowns
     */
    populateDeviceDropdowns() {
        const selects = [
            document.getElementById('deviceAssignment'),
            document.getElementById('assignDeviceSelect')
        ];
        
        selects.forEach(select => {
            if (select && this.deviceList.length > 0) {
                // Clear existing options (keep default ones)
                const defaultOptions = Array.from(select.querySelectorAll('option[value=""], option[value="all"]'));
                select.innerHTML = '';
                defaultOptions.forEach(option => select.appendChild(option));
                
                // Add device options
                this.deviceList.forEach(device => {
                    const option = document.createElement('option');
                    option.value = device.device_id;
                    option.textContent = device.display_name || device.device_name;
                    select.appendChild(option);
                });
            }
        });
    }

    /**
     * @form_submission - Handle form submission
     * @param {Event} event - Form submit event
     */
    async handleFormSubmit(event) {
        event.preventDefault();
        console.log('Upload form submitted');

        try {
            // Validate and collect file data
            const fileData = this.fileManager ? this.fileManager.getFileData() : this.getFileDataFallback();
            
            // Collect scheduling data
            const scheduleData = ScheduleManager.collectScheduleData();
            
            // Add video duration to schedule if available
            if (fileData.videoDuration) {
                scheduleData.video_duration = fileData.videoDuration;
                // Ensure display duration is at least as long as video
                scheduleData.display_duration = Math.max(scheduleData.display_duration, fileData.videoDuration);
            }

            // Validate schedule
            const validation = ScheduleManager.validateSchedule(scheduleData);
            if (!validation.isValid) {
                Utils.showNotification('Validation errors: ' + validation.errors.join(', '), 'error');
                return;
            }

            // Prepare form data
            const formData = new FormData();
            formData.append('file', fileData.file);
            formData.append('scheduling', JSON.stringify(scheduleData));

            console.log('Uploading file:', fileData.fileName);
            console.log('Schedule data:', scheduleData);

            // Show loading state
            const submitButton = this.form.querySelector('button[type="submit"]');
            Utils.setLoadingState(submitButton, true, 'Uploading...');

            // Upload file
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`Upload failed: ${response.status} ${errorText}`);
            }

            const result = await response.json();
            console.log('Upload result:', result);

            if (result.success || result.message) {
                Utils.showNotification('Content uploaded and scheduled successfully!', 'success');
                this.resetForm();
                
                // Refresh media library
                if (window.mediaLibrary) {
                    window.mediaLibrary.loadMediaList();
                }
            } else {
                throw new Error(result.error || 'Unknown upload error');
            }

        } catch (error) {
            console.error('Upload error:', error);
            Utils.showNotification('Upload failed: ' + error.message, 'error');
        } finally {
            const submitButton = this.form.querySelector('button[type="submit"]');
            Utils.setLoadingState(submitButton, false);
        }
    }

    /**
     * @file_data_fallback - Get file data without FileManager (fallback)
     * @returns {Object} File data
     */
    getFileDataFallback() {
        const fileInput = document.getElementById('file');
        const file = fileInput?.files[0];
        
        if (!file) {
            throw new Error('No file selected');
        }

        return {
            file,
            isVideo: file.type.startsWith('video/'),
            videoDuration: null,
            fileName: file.name,
            fileSize: file.size,
            fileType: file.type.startsWith('video/') ? 'video' : 'image'
        };
    }

    /**
     * @form_validation - Validate upload form
     * @returns {Object} Validation result
     */
    validateUploadForm() {
        const errors = [];

        // File validation
        const fileInput = document.getElementById('file');
        if (!fileInput || !fileInput.files[0]) {
            errors.push('Please select a file to upload');
        }

        // Display duration validation
        const displayDuration = document.getElementById('displayDuration');
        if (displayDuration) {
            const duration = parseInt(displayDuration.value);
            if (isNaN(duration) || duration < 1) {
                errors.push('Display duration must be at least 1 second');
            }
        }

        return {
            isValid: errors.length === 0,
            errors
        };
    }

    /**
     * @form_reset - Reset upload form
     */
    resetForm() {
        if (this.form) {
            this.form.reset();
        }

        // Reset file manager
        if (this.fileManager) {
            this.fileManager.resetForm();
        }

        // Reset date to today
        const startDate = document.getElementById('startDate');
        if (startDate) {
            startDate.valueAsDate = new Date();
        }

        // Clear day selections
        const dayCheckboxes = document.querySelectorAll('input[type="checkbox"][id^="day"]');
        dayCheckboxes.forEach(cb => cb.checked = false);

        // Reset display duration
        const displayDuration = document.getElementById('displayDuration');
        if (displayDuration) {
            displayDuration.value = 10;
        }
    }

    /**
     * @file_manager_integration - Set file manager instance
     * @param {FileManager} fileManager - File manager instance
     */
    setFileManager(fileManager) {
        this.fileManager = fileManager;
    }

    /**
     * @upload_progress - Handle upload progress (future enhancement)
     * @param {number} progress - Upload progress percentage
     */
    updateUploadProgress(progress) {
        // Future enhancement - show upload progress
        console.log('Upload progress:', progress + '%');
    }

    /**
     * @batch_upload - Handle multiple file upload (future enhancement)
     * @param {FileList} files - Files to upload
     */
    async handleBatchUpload(files) {
        // Future enhancement - batch upload functionality
        console.log('Batch upload to be implemented:', files.length, 'files');
    }
}

// Export for global use
window.UploadHandler = UploadHandler;