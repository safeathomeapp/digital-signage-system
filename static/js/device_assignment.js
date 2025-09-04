/**
 * @device_assignment - Device Assignment Module
 * Handles content assignment to devices and device management
 */

class DeviceAssignment {
    constructor() {
        this.modal = document.getElementById('deviceAssignModal');
        this.currentMediaId = null;
        this.devices = [];
        this.init();
    }

    /**
     * @assignment_init - Initialize device assignment module
     */
    init() {
        this.bindEvents();
        this.loadDevices();
    }

    /**
     * @assignment_events - Bind assignment events
     */
    bindEvents() {
        // Assign button event
        const assignButton = document.querySelector('[onclick*="assignToDevice"]');
        if (assignButton) {
            assignButton.removeAttribute('onclick');
            assignButton.addEventListener('click', (e) => {
                e.preventDefault();
                this.assignToDevice();
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
     * @devices_loading - Load available devices
     */
    async loadDevices() {
        try {
            this.devices = await Utils.apiRequest('/api/devices');
            this.populateDeviceDropdown();
        } catch (error) {
            console.error('Error loading devices:', error);
            Utils.showNotification('Failed to load devices: ' + error.message, 'warning');
        }
    }

    /**
     * @dropdown_population - Populate device selection dropdown
     */
    populateDeviceDropdown() {
        const select = document.getElementById('assignDeviceSelect');
        if (!select) return;

        // Clear existing options except defaults
        const defaultOptions = Array.from(select.querySelectorAll('option[value=""], option[value="all"]'));
        select.innerHTML = '';
        defaultOptions.forEach(option => select.appendChild(option));

        // Add device options
        this.devices.forEach(device => {
            const option = document.createElement('option');
            option.value = device.device_id;
            option.textContent = device.display_name || device.device_name;
            
            // Add status indicator
            if (!device.is_active) {
                option.textContent += ' (Offline)';
                option.disabled = true;
            }
            
            select.appendChild(option);
        });
    }

    /**
     * @modal_show - Show assignment modal
     * @param {number} mediaId - Media ID to assign
     */
    static showModal(mediaId) {
        const instance = window.deviceAssignment;
        if (!instance) {
            console.error('Device assignment module not initialized');
            return;
        }

        instance.currentMediaId = mediaId;
        document.getElementById('assignMediaId').value = mediaId;
        
        if (instance.modal) {
            const bsModal = new bootstrap.Modal(instance.modal);
            bsModal.show();
        }
    }

    /**
     * @content_assignment - Assign content to selected device(s)
     */
    async assignToDevice() {
        const mediaId = document.getElementById('assignMediaId').value;
        const deviceId = document.getElementById('assignDeviceSelect').value;
        const duration = document.getElementById('assignDuration').value;
        
        // Validation
        if (!deviceId) {
            Utils.showNotification('Please select a device', 'warning');
            return;
        }

        if (!mediaId) {
            Utils.showNotification('No media selected', 'error');
            return;
        }

        const durationNum = parseInt(duration);
        if (isNaN(durationNum) || durationNum < 1) {
            Utils.showNotification('Display duration must be at least 1 second', 'error');
            return;
        }

        try {
            const assignButton = document.querySelector('[onclick*="assignToDevice"]') || 
                                document.querySelector('.btn[onclick*="DeviceAssignment.assignToDevice"]');
            
            if (assignButton) {
                Utils.setLoadingState(assignButton, true, 'Assigning...');
            }

            let endpoint, requestBody;

            if (deviceId === 'all') {
                endpoint = '/api/assign-all-devices';
                requestBody = {
                    media_id: parseInt(mediaId),
                    display_duration: durationNum
                };
            } else {
                endpoint = '/api/assign-content';
                requestBody = {
                    device_id: deviceId,
                    media_id: parseInt(mediaId),
                    display_duration: durationNum
                };
            }

            const result = await Utils.apiRequest(endpoint, {
                method: 'POST',
                body: JSON.stringify(requestBody)
            });

            const message = result.success || 'Content assigned successfully';
            Utils.showNotification(message, 'success');
            this.hideModal();
            
            // Refresh media library to show updated assignment count
            if (window.mediaLibrary) {
                window.mediaLibrary.loadMediaList();
            }

        } catch (error) {
            console.error('Error assigning content:', error);
            let errorMessage = 'Assignment failed';
            
            if (error.message.includes('already assigned')) {
                errorMessage = 'Content is already assigned to this device';
            } else if (error.message.includes('device not found')) {
                errorMessage = 'Selected device not found';
            } else {
                errorMessage = 'Assignment failed: ' + error.message;
            }
            
            Utils.showNotification(errorMessage, 'error');
        } finally {
            const assignButton = document.querySelector('[onclick*="assignToDevice"]') || 
                                document.querySelector('.btn[onclick*="DeviceAssignment.assignToDevice"]');
            if (assignButton) {
                Utils.setLoadingState(assignButton, false);
            }
        }
    }

    /**
     * @assignment_removal - Remove content assignment (future enhancement)
     * @param {number} assignmentId - Assignment ID to remove
     */
    static async removeAssignment(assignmentId) {
        if (!confirm('Remove this content assignment?')) {
            return;
        }

        try {
            await Utils.apiRequest(`/api/remove-content/${assignmentId}`, {
                method: 'DELETE'
            });

            Utils.showNotification('Content assignment removed', 'success');
            
            // Refresh relevant displays
            if (window.mediaLibrary) {
                window.mediaLibrary.loadMediaList();
            }

        } catch (error) {
            console.error('Error removing assignment:', error);
            Utils.showNotification('Failed to remove assignment: ' + error.message, 'error');
        }
    }

    /**
     * @bulk_assignment - Assign multiple content items (future enhancement)
     * @param {Array} mediaIds - Array of media IDs
     * @param {string} deviceId - Target device ID
     */
    async bulkAssign(mediaIds, deviceId) {
        const results = {
            success: 0,
            failed: 0,
            errors: []
        };

        for (const mediaId of mediaIds) {
            try {
                await Utils.apiRequest('/api/assign-content', {
                    method: 'POST',
                    body: JSON.stringify({
                        device_id: deviceId,
                        media_id: mediaId,
                        display_duration: 10
                    })
                });
                results.success++;
            } catch (error) {
                results.failed++;
                results.errors.push(`Media ${mediaId}: ${error.message}`);
            }
        }

        const message = `Bulk assignment complete: ${results.success} successful, ${results.failed} failed`;
        Utils.showNotification(message, results.failed === 0 ? 'success' : 'warning');
        
        return results;
    }

    /**
     * @modal_management - Modal visibility methods
     */
    hideModal() {
        if (this.modal) {
            const bsModal = bootstrap.Modal.getInstance(this.modal);
            if (bsModal) {
                bsModal.hide();
            }
        }
    }

    showModal(mediaId) {
        DeviceAssignment.showModal(mediaId);
    }

    /**
     * @form_reset - Reset assignment form
     */
    resetForm() {
        this.currentMediaId = null;
        
        const mediaIdInput = document.getElementById('assignMediaId');
        if (mediaIdInput) mediaIdInput.value = '';
        
        const deviceSelect = document.getElementById('assignDeviceSelect');
        if (deviceSelect) deviceSelect.selectedIndex = 0;
        
        const durationInput = document.getElementById('assignDuration');
        if (durationInput) durationInput.value = '10';
    }

    /**
     * @device_status - Get device status information
     * @param {Object} device - Device object
     * @returns {Object} Status information
     */
    getDeviceStatus(device) {
        if (!device.is_active) {
            return { status: 'offline', class: 'text-danger', text: 'Offline' };
        }
        
        if (!device.last_checkin) {
            return { status: 'unknown', class: 'text-warning', text: 'Unknown' };
        }
        
        const lastCheckin = new Date(device.last_checkin);
        const timeDiff = Date.now() - lastCheckin.getTime();
        const minutesAgo = Math.floor(timeDiff / 60000);
        
        if (minutesAgo < 5) {
            return { status: 'online', class: 'text-success', text: 'Online' };
        } else if (minutesAgo < 30) {
            return { status: 'recent', class: 'text-info', text: `${minutesAgo}m ago` };
        } else {
            return { status: 'stale', class: 'text-warning', text: 'Inactive' };
        }
    }
}

// Static method for backward compatibility
DeviceAssignment.assignToDevice = function() {
    const instance = window.deviceAssignment;
    if (instance) {
        instance.assignToDevice();
    }
};

// Export for global use
window.DeviceAssignment = DeviceAssignment;