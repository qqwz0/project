/**
 * Updates the departments filter selection based on checkbox changes.
 * 
 * @param {HTMLElement} el - The checkbox element that was changed
 * @param {Array} departments - Current array of selected departments
 * @returns {Array} Updated array of selected departments
 */
window.changeDepartments = function(el, departments) {
    let department = el.value;
    if (departments.includes(department)) {
        return departments.filter(i => i !== department);
    } else {
        return [...departments, department];
    }
};
  
/**
 * Updates the positions filter selection based on checkbox changes.
 * 
 * @param {HTMLElement} el - The checkbox element that was changed
 * @param {Array} positions - Current array of selected positions
 * @returns {Array} Updated array of selected positions
 */
window.changePositions = function(el, positions) {
    let position = el.value;
    if (positions.includes(position)) {
        return positions.filter(i => i !== position);
    } else {
        return [...positions, position];
    }
};
  
/**
 * Handles changes to the 'show occupied' checkbox, updating Alpine.js data
 * and resetting the slots filter if checked.
 * 
 * @param {HTMLElement} el - The checkbox element that was changed
 */
window.handleShowOccupied = function(el) {
    const alpineData = Alpine.$data(el.closest('[x-data]'));
    alpineData.show_occupied = el.checked;
    if (el.checked) {
        alpineData.slots = null;
        const rangeInput = document.querySelector('input[type="range"]');
        rangeInput.value = rangeInput.min; // Reset to minimum value
    }
    console.log(alpineData.show_occupied);
};

/**
 * Applies all selected filters to the data and updates the filtered data.
 */
window.applyFilters = function() {
    // Get the Alpine component data
    const alpineData = Alpine.$data(document.querySelector('[x-data]'));
    
    alpineData.searchQuery = '';
    document.querySelector('.form-searching').value = '';
    alpineData.filteredData = alpineData.data.filter(i =>
        (alpineData.departments.length === 0 || alpineData.departments.includes(i.teacher.teacher_id.department)) &&
        (alpineData.positions.length === 0 || alpineData.positions.includes(i.teacher.position)) &&
        (alpineData.slots === null || i.free_slots.some(slot => slot.get_available_slots >= alpineData.slots)) &&
        (alpineData.show_occupied || i.free_slots.some(slot => slot.get_available_slots > 0))
    );

    if (window.refreshHtmxBindings) {
        window.refreshHtmxBindings();
    }
};

/**
 * Applies search filtering to the data based on teacher names.
 */
window.applySearch = function() {
    // Get the Alpine component data
    const alpineData = Alpine.$data(document.querySelector('[x-data]'));
    
    window.resetFilterUI();
    if (!alpineData.searchQuery.trim()) {
        alpineData.filteredData = alpineData.data;
        return;
    }
    
    alpineData.filteredData = alpineData.data.filter(i => {
        const fullName = (i.teacher.teacher_id.first_name + ' ' + i.teacher.teacher_id.last_name).toLowerCase();
        return fullName.includes(alpineData.searchQuery.toLowerCase().trim());
    });

    if (window.refreshHtmxBindings) {
        window.refreshHtmxBindings();
    }
};

/**
 * Resets all UI filter elements and their associated data.
 */
window.resetFilterUI = function() {
    // Get the Alpine component data
    const alpineData = Alpine.$data(document.querySelector('[x-data]'));
    
    alpineData.departments = [];
    alpineData.positions = [];
    alpineData.slots = null;
    alpineData.show_occupied = false;
    document.querySelector('.form-range').value = 0;
    document.querySelector('.form-boolean').checked = false;
    document.querySelectorAll('.form-checkbox').forEach(el => el.checked = false);
};