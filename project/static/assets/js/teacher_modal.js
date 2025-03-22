/**
 * Event listener triggered after the HTMX swap finishes inserting new content.
 * Shows a modal dialog when content is swapped into the inner_modal element.
 */
document.addEventListener('htmx:afterSwap', function(event) {
    console.log("HTMX swap завершено", event.detail.target);
    // If the content is swapped into #inner_modal, show the modal dialog.
    if (event.detail.target.id === "inner_modal") { 
        document.getElementById('details_request_modal').showModal();
    }
});

/**
 * Before swapping in new content with HTMX, if there's no response, reload the page.
 * This prevents issues when the HTMX request fails to return content.
 */
document.addEventListener('DOMContentLoaded', function() {
    initTooltips();
});

// Ініціалізація тултіпів після кожного оновлення HTMX
document.addEventListener('htmx:afterSwap', function(event) {
    console.log("HTMX swap завершено", event.detail.target);
    
    // Якщо оновили вміст - перевірити та ініціалізувати тултіп
    initTooltips();
});

// Функція для ініціалізації тултіпів
function initTooltips() {
    if (typeof bootstrap !== 'undefined') {
        let tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function(tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    } else if (typeof $ !== 'undefined') {
        $('[data-bs-toggle="tooltip"]').tooltip();
    }
}

/**
 * Closes the popup message box when the 'Close' icon is clicked.
 * This is used for Django message framework popups.
 */
function closePopup() {
  const popup = document.querySelector('.success-popup');
  popup.style.display = 'none';
}

/**
 * Reprocesses HTMX bindings for all modal buttons after filtering.
 * Should be called after Alpine.js updates the filtered data.
 */
window.refreshHtmxBindings = function() {
    // Slight timeout to ensure Alpine.js has finished rendering
    setTimeout(() => {
        document.querySelectorAll('.modal-button').forEach(button => {
            htmx.process(button);
        });
    }, 50);
};

