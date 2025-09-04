/**
 * @utils - Digital Signage Utility Functions
 * Common utility functions used throughout the application
 */

const Utils = {
    /**
     * @format_file_size - Format bytes into human readable format
     * @param {number} bytes - File size in bytes
     * @returns {string} Formatted file size
     */
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },

    /**
     * @format_duration - Format seconds into MM:SS format
     * @param {number} seconds - Duration in seconds
     * @returns {string} Formatted duration
     */
    formatDuration(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    },

    /**
     * @format_date - Format date for display
     * @param {string} dateString - Date string
     * @returns {string} Formatted date
     */
    formatDate(dateString) {
        if (!dateString) return 'Not set';
        return new Date(dateString).toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric'
        });
    },

    /**
     * @format_time - Format time for display
     * @param {string} timeString - Time string
     * @returns {string} Formatted time
     */
    formatTime(timeString) {
        if (!timeString) return 'Not set';
        return timeString;
    },

    /**
     * @debounce - Debounce function execution
     * @param {Function} func - Function to debounce
     * @param {number} wait - Wait time in milliseconds
     * @returns {Function} Debounced function
     */
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    /**
     * @throttle - Throttle function execution
     * @param {Function} func - Function to throttle
     * @param {number} limit - Time limit in milliseconds
     * @returns {Function} Throttled function
     */
    throttle(func, limit) {
        let inThrottle;
        return function(...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    },

    /**
     * @show_notification - Show notification to user
     * @param {string} message - Notification message
     * @param {string} type - Notification type (success, error, warning, info)
     */
    showNotification(message, type = 'info') {
        // Create notification element if it doesn't exist
        let container = document.getElementById('notification-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'notification-container';
            container.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 9999;
                max-width: 300px;
            `;
            document.body.appendChild(container);
        }

        // Create notification
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} alert-dismissible fade show`;
        notification.style.cssText = `
            margin-bottom: 10px;
            animation: slideInRight 0.3s ease;
        `;
        
        const typeColors = {
            success: 'success',
            error: 'danger',
            warning: 'warning',
            info: 'info'
        };

        notification.innerHTML = `
            <div class="d-flex align-items-center">
                <i class="fas fa-${type === 'success' ? 'check-circle' : 
                                   type === 'error' ? 'exclamation-triangle' :
                                   type === 'warning' ? 'exclamation-circle' : 'info-circle'} me-2"></i>
                <div>${message}</div>
                <button type="button" class="btn-close ms-auto" onclick="this.parentElement.parentElement.remove()"></button>
            </div>
        `;

        container.appendChild(notification);

        // Auto remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.style.animation = 'slideOutRight 0.3s ease';
                setTimeout(() => notification.remove(), 300);
            }
        }, 5000);
    },

    /**
     * @api_request - Make API request with error handling
     * @param {string} url - API endpoint
     * @param {Object} options - Fetch options
     * @returns {Promise} API response
     */
    async apiRequest(url, options = {}) {
        try {
            const response = await fetch(url, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }

            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            } else {
                return await response.text();
            }
        } catch (error) {
            console.error('API Request failed:', error);
            throw error;
        }
    },

    /**
     * @validate_form - Validate form fields
     * @param {Object} fields - Field validation rules
     * @returns {Object} Validation result
     */
    validateForm(fields) {
        const errors = {};
        let isValid = true;

        for (const [fieldName, rules] of Object.entries(fields)) {
            const element = document.getElementById(fieldName);
            if (!element) continue;

            const value = element.type === 'checkbox' ? element.checked : element.value;

            // Required validation
            if (rules.required && !value) {
                errors[fieldName] = 'This field is required';
                isValid = false;
                continue;
            }

            // Min/Max length validation
            if (rules.minLength && value.length < rules.minLength) {
                errors[fieldName] = `Minimum length is ${rules.minLength}`;
                isValid = false;
            }

            if (rules.maxLength && value.length > rules.maxLength) {
                errors[fieldName] = `Maximum length is ${rules.maxLength}`;
                isValid = false;
            }

            // Numeric validation
            if (rules.numeric && isNaN(value)) {
                errors[fieldName] = 'Must be a number';
                isValid = false;
            }

            // Custom validation
            if (rules.custom && !rules.custom(value)) {
                errors[fieldName] = rules.message || 'Invalid value';
                isValid = false;
            }
        }

        return { isValid, errors };
    },

    /**
     * @loading_state - Show/hide loading state on element
     * @param {HTMLElement} element - Target element
     * @param {boolean} loading - Loading state
     * @param {string} text - Loading text
     */
    setLoadingState(element, loading, text = 'Loading...') {
        if (loading) {
            element.disabled = true;
            element.dataset.originalText = element.innerHTML;
            element.innerHTML = `
                <span class="spinner-border spinner-border-sm me-2" role="status"></span>
                ${text}
            `;
        } else {
            element.disabled = false;
            element.innerHTML = element.dataset.originalText || element.innerHTML;
        }
    }
};

// Add CSS animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOutRight {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
`;
document.head.appendChild(style);