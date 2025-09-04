/**
 * @file_manager - File Upload and Management Module
 * Handles file selection, validation, and metadata extraction
 */

class FileManager {
    constructor() {
        this.currentVideoElement = null;
        this.allowedTypes = {
            image: ['png', 'jpg', 'jpeg', 'gif'],
            video: ['mp4', 'mov', 'avi', 'webm', 'mkv']
        };
        this.init();
    }

    /**
     * @file_init - Initialize file manager
     */
    init() {
        this.bindEvents();
    }

    /**
     * @file_events - Bind file input events
     */
    bindEvents() {
        const fileInput = document.getElementById('file');
        if (fileInput) {
            fileInput.addEventListener('change', (e) => this.handleFileSelection(e));
        }
    }

    /**
     * @file_selection - Handle file selection event
     * @param {Event} event - File input change event
     */
    handleFileSelection(event) {
        const file = event.target.files[0];
        console.log('File selected:', file?.name);
        
        if (file) {
            if (this.validateFile(file)) {
                this.displayFileInfo(file);
            } else {
                this.hideFileInfo();
                Utils.showNotification('Invalid file type. Please select a valid image or video file.', 'error');
            }
        } else {
            this.hideFileInfo();
        }
    }

    /**
     * @file_validation - Validate selected file
     * @param {File} file - Selected file
     * @returns {boolean} Is file valid
     */
    validateFile(file) {
        if (!file) return false;
        
        const extension = file.name.split('.').pop().toLowerCase();
        const allAllowed = [...this.allowedTypes.image, ...this.allowedTypes.video];
        
        return allAllowed.includes(extension);
    }

    /**
     * @file_info_display - Display file information
     * @param {File} file - Selected file
     */
    displayFileInfo(file) {
        const elements = this.getFileInfoElements();
        
        elements.fileName.textContent = file.name;
        elements.fileSize.textContent = Utils.formatFileSize(file.size);
        
        const isVideo = this.isVideoFile(file);
        elements.fileType.textContent = isVideo ? 'Video' : 'Image';

        if (isVideo) {
            this.showVideoInfo();
            this.loadVideoMetadata(file);
        } else {
            this.hideVideoInfo();
            this.resetDisplayDuration();
        }

        this.showFileInfo();
    }

    /**
     * @file_info_elements - Get file info DOM elements
     * @returns {Object} File info elements
     */
    getFileInfoElements() {
        return {
            fileInfo: document.getElementById('fileInfo'),
            fileName: document.getElementById('fileName'),
            fileSize: document.getElementById('fileSize'),
            fileType: document.getElementById('fileType'),
            videoInfo: document.getElementById('videoInfo'),
            videoMinDuration: document.getElementById('videoMinDuration')
        };
    }

    /**
     * @video_detection - Check if file is a video
     * @param {File} file - File to check
     * @returns {boolean} Is video file
     */
    isVideoFile(file) {
        const extension = file.name.split('.').pop().toLowerCase();
        return this.allowedTypes.video.includes(extension) || file.type.startsWith('video/');
    }

    /**
     * @video_metadata - Load and display video metadata
     * @param {File} file - Video file
     */
    loadVideoMetadata(file) {
        // Clean up previous video element
        if (this.currentVideoElement) {
            this.currentVideoElement.remove();
            this.currentVideoElement = null;
        }

        this.currentVideoElement = document.createElement('video');
        this.currentVideoElement.preload = 'metadata';
        this.currentVideoElement.style.display = 'none';
        
        this.currentVideoElement.onloadedmetadata = () => {
            const duration = Math.ceil(this.currentVideoElement.duration);
            const resolution = `${this.currentVideoElement.videoWidth}x${this.currentVideoElement.videoHeight}`;
            
            this.displayVideoMetadata(duration, resolution);
            this.updateDisplayDuration(duration);
        };

        this.currentVideoElement.onerror = () => {
            console.error('Error loading video metadata');
            Utils.showNotification('Could not load video metadata', 'warning');
        };

        this.currentVideoElement.src = URL.createObjectURL(file);
        document.body.appendChild(this.currentVideoElement);
    }

    /**
     * @video_metadata_display - Display video metadata in UI
     * @param {number} duration - Video duration in seconds
     * @param {string} resolution - Video resolution
     */
    displayVideoMetadata(duration, resolution) {
        const videoDuration = document.getElementById('videoDuration');
        const videoResolution = document.getElementById('videoResolution');
        const videoLength = document.getElementById('videoLength');

        if (videoDuration) videoDuration.textContent = Utils.formatDuration(duration);
        if (videoResolution) videoResolution.textContent = resolution;
        if (videoLength) videoLength.textContent = `${duration}s`;
    }

    /**
     * @display_duration_update - Update display duration based on video length
     * @param {number} videoDuration - Video duration in seconds
     */
    updateDisplayDuration(videoDuration) {
        const durationInput = document.getElementById('displayDuration');
        if (durationInput) {
            durationInput.min = videoDuration;
            const currentValue = parseInt(durationInput.value) || 10;
            durationInput.value = Math.max(videoDuration, currentValue);
        }
    }

    /**
     * @ui_show_hide - UI visibility methods
     */
    showFileInfo() {
        const fileInfo = document.getElementById('fileInfo');
        if (fileInfo) {
            fileInfo.style.display = 'block';
            fileInfo.classList.add('show');
        }
    }

    hideFileInfo() {
        const fileInfo = document.getElementById('fileInfo');
        if (fileInfo) {
            fileInfo.style.display = 'none';
            fileInfo.classList.remove('show');
        }
    }

    showVideoInfo() {
        const videoInfo = document.getElementById('videoInfo');
        const videoMinDuration = document.getElementById('videoMinDuration');
        
        if (videoInfo) videoInfo.style.display = 'block';
        if (videoMinDuration) videoMinDuration.style.display = 'block';
    }

    hideVideoInfo() {
        const videoInfo = document.getElementById('videoInfo');
        const videoMinDuration = document.getElementById('videoMinDuration');
        
        if (videoInfo) videoInfo.style.display = 'none';
        if (videoMinDuration) videoMinDuration.style.display = 'none';
    }

    /**
     * @duration_reset - Reset display duration to default
     */
    resetDisplayDuration() {
        const durationInput = document.getElementById('displayDuration');
        if (durationInput) {
            durationInput.min = 1;
            durationInput.value = 10;
        }
    }

    /**
     * @file_data_export - Get file data for upload
     * @returns {Object} File upload data
     */
    getFileData() {
        const fileInput = document.getElementById('file');
        const file = fileInput?.files[0];
        
        if (!file) {
            throw new Error('No file selected');
        }

        if (!this.validateFile(file)) {
            throw new Error('Invalid file type');
        }

        const videoDuration = this.currentVideoElement?.duration ? 
            Math.ceil(this.currentVideoElement.duration) : null;

        return {
            file,
            isVideo: this.isVideoFile(file),
            videoDuration,
            fileName: file.name,
            fileSize: file.size,
            fileType: this.isVideoFile(file) ? 'video' : 'image'
        };
    }

    /**
     * @cleanup - Clean up resources
     */
    cleanup() {
        if (this.currentVideoElement) {
            this.currentVideoElement.remove();
            this.currentVideoElement = null;
        }
    }

    /**
     * @form_reset - Reset file form
     */
    resetForm() {
        const fileInput = document.getElementById('file');
        if (fileInput) {
            fileInput.value = '';
        }
        
        this.hideFileInfo();
        this.resetDisplayDuration();
        this.cleanup();
    }
}

// Export for global use
window.FileManager = FileManager;