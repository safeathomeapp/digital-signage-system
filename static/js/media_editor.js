/**
 * @media_editor - Media Editing Module
 * Handles editing of existing media scheduling and properties
 */

class MediaEditor {
    constructor() {
        this.modal = document.getElementById('editMediaModal');
        this.form = document.getElementById('editMediaForm');
        this.currentMediaId = null;
        this.init();
    }

    /**
     * @editor_init - Initialize media editor
     */
    init() {
        this.bindEvents();
    }

    /**
     * @editor_events - Bind editor events
     */
    bindEvents() {
        // Save button event
        const saveButton = document.querySelector('[onclick*="saveMediaEdit"]');
        if (saveButton) {
            saveButton.addEventListener('click', (e) => {
                e.preventDefault();
                this.saveMediaEdit();
            });
        }

        // Form submit event
        if (this.form) {
            this.form.addEventListener('submit', (e) => {
                e.preventDefault();
                this.saveMediaEdit();
            });
        }

        // Modal events
        if (this.modal) {
            this.modal.addEventListener('hidden.bs.modal', () => {
                this.resetForm();
            });
        }
    }

    /**
     * @edit_media - Open edit modal for media item
     * @param {number} mediaId - Media ID to edit
     */
    static async editMedia(mediaId) {
        const editor = window.mediaEditor;
        if (!editor) {
            console.error('Media editor not initialized');
            return;
        }

        try {
            await editor.loadMediaData(mediaId);
            editor.showModal();
        } catch (error) {
            console.error('Error loading media for editing:', error);
            Utils.showNotification('Failed to load media data: ' + error.message, 'error');
        }
    }

    /**
     * @media_data_loading - Load media data from server
     * @param {number} mediaId - Media ID to load
     */
    async loadMediaData(mediaId) {
        this.currentMediaId = mediaId;
        
        // Get detailed media list to find our media
        const mediaList = await Utils.apiRequest('/api/media/detailed');
        const media = mediaList.find(m => m.id === mediaId);
        
        if (!media) {
            throw new Error('Media not found');
        }

        this.populateForm(media);
    }

    /**
     * @form_population - Populate form with media data
     * @param {Object} media - Media data
     */
    populateForm(media) {
        // Set basic fields
        document.getElementById('editMediaId').value = media.id;
        
        const displayDuration = document.getElementById('editDisplayDuration');
        if (displayDuration) {
            displayDuration.value = media.display_duration || 10;
        }

        const startTime = document.getElementById('editStartTime');
        if (startTime) {
            startTime.value = media.start_time || '';
        }

        const endTime = document.getElementById('editEndTime');
        if (endTime) {
            endTime.value = media.end_time || '';
        }

        const startDate = document.getElementById('editStartDate');
        if (startDate) {
            startDate.value = media.start_date || '';
        }

        const endDate = document.getElementById('editEndDate');
        if (endDate) {
            endDate.value = media.end_date || '';
        }

        // Set days of week
        this.populateDaysOfWeek(media.days_of_week);
    }

    /**
     * @days_population - Populate days of week checkboxes
     * @param {string} daysJson - JSON string of selected days
     */
    populateDaysOfWeek(daysJson) {
        let daysArray = [];
        
        if (daysJson) {
            try {
                daysArray = JSON.parse(daysJson);
            } catch (e) {
                console.warn('Invalid days JSON:', daysJson);
                daysArray = ['all'];
            }
        } else {
            daysArray = ['all'];
        }

        ScheduleManager.populateDays(daysArray, 'editDay');
    }

    /**
     * @form_data_collection - Collect form data for saving
     * @returns {Object} Form data
     */
    collectFormData() {
        const selectedDays = ScheduleManager.getSelectedDays('editDay');
        
        return {
            days_of_week: selectedDays.length > 0 ? selectedDays : ['all'],
            display_duration: parseInt(document.getElementById('editDisplayDuration').value) || 10,
            start_time: document.getElementById('editStartTime').value || null,
            end_time: document.getElementById('editEndTime').value || null,
            start_date: document.getElementById('editStartDate').value || null,
            end_date: document.getElementById('editEndDate').value || null
        };
    }

    /**
     * @media_save - Save media edits
     */
    async saveMediaEdit() {
        if (!this.currentMediaId) {
            Utils.showNotification('No media selected for editing', 'error');
            return;
        }

        try {
            const formData = this.collectFormData();
            
            // Validate form data
            const validation = ScheduleManager.validateSchedule(formData);
            if (!validation.isValid) {
                Utils.showNotification('Validation errors: ' + validation.errors.join(', '), 'error');
                return;
            }

            // Show loading state
            const saveButton = document.querySelector('[onclick*="saveMediaEdit"]');
            Utils.setLoadingState(saveButton, true, 'Saving...');

            // Save to server
            await Utils.apiRequest(`/api/media/${this.currentMediaId}/schedule`, {
                method: 'PUT',
                body: JSON.stringify(formData)
            });

            Utils.showNotification('Media schedule updated successfully', 'success');
            this.hideModal();
            
            // Refresh media library
            if (window.mediaLibrary) {
                window.mediaLibrary.loadMediaList();
            }

        } catch (error) {
            console.error('Error saving media edit:', error);
            Utils.showNotification('Failed to save changes: ' + error.message, 'error');
        } finally {
            const saveButton = document.querySelector('[onclick*="saveMediaEdit"]');
            Utils.setLoadingState(saveButton, false);
        }
    }

    /**
     * @modal_management - Modal show/hide methods
     */
    showModal() {
        if (this.modal) {
            const bsModal = new bootstrap.Modal(this.modal);
            bsModal.show();
        }
    }

    hideModal() {
        if (this.modal) {
            const bsModal = bootstrap.Modal.getInstance(this.modal);
            if (bsModal) {
                bsModal.hide();
            }
        }
    }

    /**
     * @form_reset - Reset form to default state
     */
    resetForm() {
        this.currentMediaId = null;
        
        if (this.form) {
            this.form.reset();
        }

        // Clear all day checkboxes
        const checkboxes = document.querySelectorAll('input[type="checkbox"][id^="editDay"]');
        checkboxes.forEach(cb => cb.checked = false);

        // Reset select values
        const selects = document.querySelectorAll('#editMediaModal select');
        selects.forEach(select => select.selectedIndex = 0);
    }

    /**
     * @validation_display - Display validation errors
     * @param {Array} errors - Array of error messages
     */
    displayValidationErrors(errors) {
        // Remove existing error displays
        const existingErrors = document.querySelectorAll('.validation-error');
        existingErrors.forEach(error => error.remove());

        // Add new error displays
        errors.forEach(error => {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'alert alert-danger alert-sm validation-error';
            errorDiv.textContent = error;
            
            const formBody = document.querySelector('#editMediaModal .modal-body');
            if (formBody) {
                formBody.insertBefore(errorDiv, formBody.firstChild);
            }
        });
    }

    /**
     * @field_validation - Validate individual form field
     * @param {string} fieldId - Field ID to validate
     * @returns {boolean} Is field valid
     */
    validateField(fieldId) {
        const field = document.getElementById(fieldId);
        if (!field) return true;

        let isValid = true;
        let errorMessage = '';

        switch (fieldId) {
            case 'editDisplayDuration':
                const duration = parseInt(field.value);
                if (isNaN(duration) || duration < 1) {
                    isValid = false;
                    errorMessage = 'Display duration must be at least 1 second';
                }
                break;

            case 'editStartDate':
            case 'editEndDate':
                const startDate = document.getElementById('editStartDate').value;
                const endDate = document.getElementById('editEndDate').value;
                
                if (startDate && endDate && new Date(startDate) > new Date(endDate)) {
                    isValid = false;
                    errorMessage = 'Start date cannot be after end date';
                }
                break;

            case 'editStartTime':
            case 'editEndTime':
                const startTime = document.getElementById('editStartTime').value;
                const endTime = document.getElementById('editEndTime').value;
                
                if (startTime && endTime && startTime >= endTime) {
                    isValid = false;
                    errorMessage = 'Start time must be before end time';
                }
                break;
        }

        this.showFieldError(field, isValid ? null : errorMessage);
        return isValid;
    }

    /**
     * @field_error_display - Show/hide field error
     * @param {HTMLElement} field - Field element
     * @param {string|null} message - Error message or null to clear
     */
    showFieldError(field, message) {
        // Remove existing error
        const existingError = field.parentNode.querySelector('.field-error');
        if (existingError) {
            existingError.remove();
        }

        if (message) {
            // Add error styling
            field.classList.add('is-invalid');
            
            // Add error message
            const errorDiv = document.createElement('div');
            errorDiv.className = 'field-error text-danger small mt-1';
            errorDiv.textContent = message;
            field.parentNode.appendChild(errorDiv);
        } else {
            // Remove error styling
            field.classList.remove('is-invalid');
        }
    }
}

// Export for global use
window.MediaEditor = MediaEditor;