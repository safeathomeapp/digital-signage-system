/**
 * @schedule_manager - Schedule Management Module
 * Handles day selection, time ranges, and date calculations
 */

class ScheduleManager {
    /**
     * @day_presets - Apply day selection presets
     * @param {string} preset - Preset type (all, weekdays, weekends)
     * @param {string} prefix - Element ID prefix (day or editDay)
     */
    static applyDayPreset(prefix = 'day') {
        const presetSelect = document.getElementById(`${prefix}Preset`);
        if (!presetSelect) return;

        const preset = presetSelect.value;
        const checkboxes = document.querySelectorAll(`input[type="checkbox"][id^="${prefix}"]`);
        
        // Clear all checkboxes first
        checkboxes.forEach(cb => cb.checked = false);
        
        switch(preset) {
            case 'all':
                checkboxes.forEach(cb => cb.checked = true);
                break;
            case 'weekdays':
                ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'].forEach(day => {
                    const checkbox = document.getElementById(`${prefix}${day}`);
                    if (checkbox) checkbox.checked = true;
                });
                break;
            case 'weekends':
                ['Sat', 'Sun'].forEach(day => {
                    const checkbox = document.getElementById(`${prefix}${day}`);
                    if (checkbox) checkbox.checked = true;
                });
                break;
        }

        // Trigger change event for validation
        checkboxes.forEach(cb => {
            cb.dispatchEvent(new Event('change'));
        });
    }

    /**
     * @edit_day_presets - Apply day presets for edit modal
     */
    static applyEditDayPreset() {
        this.applyDayPreset('editDay');
    }

    /**
     * @date_calculation - Calculate end date based on duration
     */
    static calculateEndDate() {
        const startDateInput = document.getElementById('startDate');
        const rangeSelect = document.getElementById('dateRange');
        const endDateInput = document.getElementById('endDate');
        
        if (!startDateInput || !rangeSelect || !endDateInput) return;

        const startDate = startDateInput.value;
        const rangeValue = rangeSelect.value;
        
        if (rangeValue === 'custom') {
            endDateInput.readOnly = false;
            endDateInput.style.backgroundColor = '';
            return;
        }
        
        endDateInput.readOnly = true;
        endDateInput.style.backgroundColor = '#f8f9fa';
        
        if (startDate && rangeValue && rangeValue !== 'custom') {
            const start = new Date(startDate);
            const months = parseInt(rangeValue);
            const end = new Date(start.getFullYear(), start.getMonth() + months, start.getDate());
            endDateInput.value = end.toISOString().split('T')[0];
        } else {
            endDateInput.value = '';
        }
    }

    /**
     * @schedule_data_collection - Collect scheduling data from form
     * @param {string} prefix - Form element prefix
     * @returns {Object} Schedule data
     */
    static collectScheduleData(prefix = '') {
        const selectedDays = this.getSelectedDays(prefix);
        const displayDuration = document.getElementById(`${prefix}displayDuration`)?.value;
        const startTime = document.getElementById(`${prefix}startTime`)?.value;
        const endTime = document.getElementById(`${prefix}endTime`)?.value;
        const startDate = document.getElementById(`${prefix}startDate`)?.value;
        const endDate = document.getElementById(`${prefix}endDate`)?.value;
        const deviceAssignment = document.getElementById(`${prefix}deviceAssignment`)?.value;

        return {
            days_of_week: selectedDays.length > 0 ? selectedDays : ['all'],
            display_duration: parseInt(displayDuration) || 10,
            start_time: startTime || null,
            end_time: endTime || null,
            start_date: startDate || null,
            end_date: endDate || null,
            device_assignment: deviceAssignment || null
        };
    }

    /**
     * @selected_days - Get selected days from checkboxes
     * @param {string} prefix - Checkbox prefix
     * @returns {Array} Selected days
     */
    static getSelectedDays(prefix = 'day') {
        const selectedDays = [];
        const checkboxes = document.querySelectorAll(`input[type="checkbox"][id^="${prefix}"]:checked`);
        
        checkboxes.forEach(cb => {
            selectedDays.push(cb.value);
        });
        
        return selectedDays;
    }

    /**
     * @days_population - Populate day checkboxes from data
     * @param {Array} daysArray - Days to select
     * @param {string} prefix - Checkbox prefix
     */
    static populateDays(daysArray, prefix = 'editDay') {
        const checkboxes = document.querySelectorAll(`input[type="checkbox"][id^="${prefix}"]`);
        
        // Clear all checkboxes first
        checkboxes.forEach(cb => cb.checked = false);
        
        if (!daysArray || daysArray.length === 0 || daysArray.includes('all')) {
            // Select all days
            checkboxes.forEach(cb => cb.checked = true);
            return;
        }
        
        // Select specific days
        daysArray.forEach(day => {
            const dayCapitalized = day.charAt(0).toUpperCase() + day.slice(1);
            const checkbox = document.getElementById(`${prefix}${dayCapitalized}`);
            if (checkbox) checkbox.checked = true;
        });
    }

    /**
     * @schedule_validation - Validate schedule data
     * @param {Object} scheduleData - Schedule data to validate
     * @returns {Object} Validation result
     */
    static validateSchedule(scheduleData) {
        const errors = [];

        // Display duration validation
        if (scheduleData.display_duration < 1) {
            errors.push('Display duration must be at least 1 second');
        }

        // Date range validation
        if (scheduleData.start_date && scheduleData.end_date) {
            const startDate = new Date(scheduleData.start_date);
            const endDate = new Date(scheduleData.end_date);
            
            if (startDate > endDate) {
                errors.push('Start date cannot be after end date');
            }
        }

        // Time range validation
        if (scheduleData.start_time && scheduleData.end_time) {
            const startTime = scheduleData.start_time;
            const endTime = scheduleData.end_time;
            
            if (startTime >= endTime) {
                errors.push('Start time must be before end time');
            }
        }

        return {
            isValid: errors.length === 0,
            errors
        };
    }

    /**
     * @schedule_formatting - Format schedule data for display
     * @param {Object} media - Media object with schedule data
     * @returns {Object} Formatted schedule display data
     */
    static formatScheduleDisplay(media) {
        return {
            days: this.formatDaysOfWeek(media.days_of_week),
            duration: `${media.display_duration || 10}s`,
            dateRange: this.formatDateRange(media.start_date, media.end_date),
            timeRange: this.formatTimeRange(media.start_time, media.end_time)
        };
    }

    /**
     * @days_formatting - Format days of week for display
     * @param {string} daysJson - JSON string of days
     * @returns {string} Formatted days
     */
    static formatDaysOfWeek(daysJson) {
        if (!daysJson) return 'All days';
        
        try {
            const days = JSON.parse(daysJson);
            if (days.includes('all') || days.length === 7) return 'All days';
            if (days.includes('weekdays')) return 'Weekdays';
            if (days.includes('weekends')) return 'Weekends';
            
            return days.map(day => day.toUpperCase()).join(', ');
        } catch {
            return 'All days';
        }
    }

    /**
     * @date_range_formatting - Format date range for display
     * @param {string} startDate - Start date
     * @param {string} endDate - End date
     * @returns {string} Formatted date range
     */
    static formatDateRange(startDate, endDate) {
        if (!startDate && !endDate) return 'No date limits';
        if (!startDate) return `Until ${Utils.formatDate(endDate)}`;
        if (!endDate) return `From ${Utils.formatDate(startDate)}`;
        return `${Utils.formatDate(startDate)} - ${Utils.formatDate(endDate)}`;
    }

    /**
     * @time_range_formatting - Format time range for display
     * @param {string} startTime - Start time
     * @param {string} endTime - End time
     * @returns {string} Formatted time range
     */
    static formatTimeRange(startTime, endTime) {
        if (!startTime && !endTime) return 'All day';
        const start = startTime || '00:00';
        const end = endTime || '23:59';
        return `${start} - ${end}`;
    }

    /**
     * @form_initialization - Initialize schedule form
     */
    static initializeForm() {
        // Set default start date to today
        const startDateInput = document.getElementById('startDate');
        if (startDateInput) {
            startDateInput.valueAsDate = new Date();
        }

        // Bind event listeners
        this.bindEvents();
    }

    /**
     * @event_binding - Bind schedule-related events
     */
    static bindEvents() {
        // Day preset changes
        const dayPreset = document.getElementById('dayPreset');
        if (dayPreset) {
            dayPreset.addEventListener('change', () => this.applyDayPreset());
        }

        const editDayPreset = document.getElementById('editDayPreset');
        if (editDayPreset) {
            editDayPreset.addEventListener('change', () => this.applyEditDayPreset());
        }

        // Date range calculations
        const dateRange = document.getElementById('dateRange');
        if (dateRange) {
            dateRange.addEventListener('change', () => this.calculateEndDate());
        }

        const startDate = document.getElementById('startDate');
        if (startDate) {
            startDate.addEventListener('change', () => this.calculateEndDate());
        }
    }
}

// Initialize when DOM is loaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        ScheduleManager.initializeForm();
    });
} else {
    ScheduleManager.initializeForm();
}

// Export for global use
window.ScheduleManager = ScheduleManager;