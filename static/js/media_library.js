/**
 * @media_library - Media Library Management Module
 * Handles media list display, status management, and library operations
 */

class MediaLibrary {
    constructor() {
        this.mediaContainer = document.getElementById('mediaList');
        this.refreshButton = document.querySelector('[onclick*="loadMediaList"]');
        this.init();
    }

    /**
     * @library_init - Initialize media library
     */
    init() {
        this.bindEvents();
        this.loadMediaList();
    }

    /**
     * @library_events - Bind library events
     */
    bindEvents() {
        if (this.refreshButton) {
            this.refreshButton.addEventListener('click', () => {
                this.loadMediaList();
            });
        }
    }

    /**
     * @media_loading - Load media list from server
     */
    async loadMediaList() {
        if (!this.mediaContainer) return;

        try {
            this.showLoading();
            const mediaList = await Utils.apiRequest('/api/media/detailed');
            
            if (mediaList.length === 0) {
                this.showEmptyState();
                return;
            }

            this.renderMediaList(mediaList);
        } catch (error) {
            console.error('Error loading media list:', error);
            this.showErrorState(error.message);
            Utils.showNotification('Failed to load media library: ' + error.message, 'error');
        }
    }

    /**
     * @media_rendering - Render media list in UI
     * @param {Array} mediaList - List of media items
     */
    renderMediaList(mediaList) {
        const html = mediaList.map(media => this.createMediaItemHTML(media)).join('');
        this.mediaContainer.innerHTML = html;
    }

    /**
     * @media_item_html - Create HTML for single media item
     * @param {Object} media - Media item data
     * @returns {string} HTML string
     */
    createMediaItemHTML(media) {
        const status = this.getMediaStatus(media);
        const fileSize = Utils.formatFileSize(media.file_size);
        const uploadDate = Utils.formatDate(media.created_at);
        const thumbnail = this.createThumbnail(media);
        const schedule = ScheduleManager.formatScheduleDisplay(media);

        return `
            <div class="media-item" data-media-id="${media.id}">
                <div class="row align-items-start">
                    <div class="col-auto">
                        ${thumbnail}
                    </div>
                    <div class="col">
                        <!-- Title row with status and filename -->
                        <div class="row media-title-row align-items-center">
                            <div class="col">
                                <i class="${status.icon} status-icon ${status.class}" title="${status.text}"></i>
                                <strong>${this.escapeHtml(media.original_name)}</strong>
                            </div>
                        </div>
                        
                        <!-- File info row -->
                        <div class="row media-meta-row">
                            <div class="col">
                                ${media.file_type} • ${fileSize} • ${uploadDate}
                            </div>
                        </div>
                        
                        <!-- Schedule info row -->
                        <div class="row media-schedule-row">
                            <div class="col-12">
                                <span class="info-tag">
                                    <i class="fas fa-calendar-day"></i>${schedule.days}
                                </span>
                                <span class="info-tag">
                                    <i class="fas fa-clock"></i>${schedule.duration}
                                </span>
                                <span class="info-tag">
                                    <i class="fas fa-calendar"></i>${schedule.dateRange}
                                </span>
                                <span class="info-tag">
                                    <i class="fas fa-clock"></i>${schedule.timeRange}
                                </span>
                            </div>
                        </div>
                    </div>
                    <div class="col-auto">
                        <button class="btn btn-info btn-sm devices-popup me-2" 
                                onclick="DeviceAssignment.showModal(${media.id})" 
                                title="Assign to devices">
                            <i class="fas fa-tv"></i> ${media.assignment_count}
                        </button>
                    </div>
                    <div class="col-auto">
                        <div class="form-check form-switch">
                            <input class="form-check-input" type="checkbox" 
                                   ${media.is_active ? 'checked' : ''} 
                                   onchange="MediaLibrary.toggleMediaStatus(${media.id}, ${media.is_active})" 
                                   title="Active/Inactive">
                        </div>
                    </div>
                    <div class="col-auto">
                        <button class="btn btn-outline-secondary btn-sm me-2" 
                                onclick="MediaEditor.editMedia(${media.id})" 
                                title="Edit">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="btn btn-outline-danger btn-sm" 
                                onclick="MediaLibrary.deleteMedia(${media.id}, '${this.escapeHtml(media.original_name)}')" 
                                title="Delete">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * @thumbnail_creation - Create thumbnail HTML for media item
     * @param {Object} media - Media item data
     * @returns {string} Thumbnail HTML
     */
    createThumbnail(media) {
        if (media.file_type === 'image') {
            return `<img src="/uploads/${media.filename}" class="media-thumbnail" alt="Thumbnail" loading="lazy">`;
        } else {
            return `<div class="thumbnail-placeholder"><i class="fas fa-video"></i></div>`;
        }
    }

    /**
     * @media_status - Get media status information
     * @param {Object} media - Media item data
     * @returns {Object} Status information
     */
    getMediaStatus(media) {
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

    /**
     * @status_toggle - Toggle media active/inactive status
     * @param {number} mediaId - Media ID
     * @param {boolean} currentStatus - Current status
     */
    static async toggleMediaStatus(mediaId, currentStatus) {
        try {
            const newStatus = !currentStatus;
            
            await Utils.apiRequest(`/api/media/${mediaId}/toggle`, {
                method: 'PUT',
                body: JSON.stringify({ is_active: newStatus })
            });
            
            Utils.showNotification(
                `Media ${newStatus ? 'activated' : 'deactivated'} successfully`, 
                'success'
            );
            
            // Reload media list to show updated status
            if (window.mediaLibrary) {
                window.mediaLibrary.loadMediaList();
            }
            
        } catch (error) {
            console.error('Error toggling media status:', error);
            Utils.showNotification('Failed to update media status: ' + error.message, 'error');
        }
    }

    /**
     * @media_deletion - Delete media item
     * @param {number} mediaId - Media ID
     * @param {string} filename - Media filename
     */
    static async deleteMedia(mediaId, filename) {
        if (!confirm(`Delete "${filename}"? This will remove it from all devices and cannot be undone.`)) {
            return;
        }
        
        try {
            await Utils.apiRequest(`/api/media/${mediaId}`, {
                method: 'DELETE'
            });
            
            Utils.showNotification('Media deleted successfully', 'success');
            
            // Reload media list
            if (window.mediaLibrary) {
                window.mediaLibrary.loadMediaList();
            }
            
        } catch (error) {
            console.error('Error deleting media:', error);
            Utils.showNotification('Failed to delete media: ' + error.message, 'error');
        }
    }

    /**
     * @ui_states - UI state management methods
     */
    showLoading() {
        this.mediaContainer.innerHTML = `
            <div class="text-center py-5">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <p class="mt-2 text-muted">Loading media library...</p>
            </div>
        `;
    }

    showEmptyState() {
        this.mediaContainer.innerHTML = `
            <div class="text-center py-5">
                <i class="fas fa-photo-video fa-3x text-muted mb-3"></i>
                <h5 class="text-muted">No media uploaded yet</h5>
                <p class="text-muted">Upload your first image or video to get started</p>
            </div>
        `;
    }

    showErrorState(errorMessage) {
        this.mediaContainer.innerHTML = `
            <div class="text-center py-5">
                <i class="fas fa-exclamation-triangle fa-3x text-danger mb-3"></i>
                <h5 class="text-danger">Error loading media library</h5>
                <p class="text-muted">${this.escapeHtml(errorMessage)}</p>
                <button class="btn btn-primary" onclick="window.mediaLibrary.loadMediaList()">
                    <i class="fas fa-sync me-1"></i>Try Again
                </button>
            </div>
        `;
    }

    /**
     * @html_escape - Escape HTML to prevent XSS
     * @param {string} text - Text to escape
     * @returns {string} Escaped text
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * @media_refresh - Refresh media list
     */
    refresh() {
        this.loadMediaList();
    }

    /**
     * @media_search - Search media items (future enhancement)
     * @param {string} query - Search query
     */
    searchMedia(query) {
        // Future enhancement - implement search functionality
        console.log('Search functionality to be implemented:', query);
    }

    /**
     * @media_filter - Filter media items (future enhancement)
     * @param {string} filter - Filter type
     */
    filterMedia(filter) {
        // Future enhancement - implement filter functionality
        console.log('Filter functionality to be implemented:', filter);
    }
}

// Export for global use
window.MediaLibrary = MediaLibrary;