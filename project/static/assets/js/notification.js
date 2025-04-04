function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
}

// Helper function to mark a message as read
function markMessageAsRead(messageElement) {
    if (!messageElement || messageElement.classList.contains('read')) return;
    
    const messageId = messageElement.dataset.id;
    if (!messageId) return;
    
    fetch(`/notifications/read/${messageId}/`, {
        method: "POST",
        headers: {
            "X-CSRFToken": getCookie("csrftoken"), 
            "Content-Type": "application/json"
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.is_read) {
            messageElement.classList.add("read");
        }
    })
    .catch(error => {
        console.error(`Error marking message ${messageId} as read:`, error);
    });
}

document.addEventListener('DOMContentLoaded', () => {
    const notificationToggleBtn = document.getElementById('dropdownMenuButton');
    const notificationDropdown = document.getElementById('notification-list');
    const notificationDot = document.getElementById('notification-indicator');
    const messageToggleBtn = document.getElementById('messageDropdownButton');
    const messagePopup = document.getElementById('message-popup');
    const messageIndicator = document.getElementById('message-indicator');
    
    // Notification dropdown click handler
    if (notificationToggleBtn && notificationDropdown) {
        notificationToggleBtn.addEventListener('click', event => {
            event.preventDefault();
            
            // Close message popup if it's open
            if (messagePopup && messagePopup.classList.contains('show')) {
                messagePopup.classList.remove('show');
            }
            
            // Toggle notification dropdown
            notificationDropdown.classList.toggle('show');
            
            // Hide notification dot when opened
            if (notificationDropdown.classList.contains('show')) {
                notificationDot.style.display = 'none';
            }
        });
    }
    
    // Message popup click handler
    if (messageToggleBtn && messagePopup) {
        messageToggleBtn.addEventListener('click', event => {
            event.preventDefault();
            
            // Close notification dropdown if it's open
            if (notificationDropdown && notificationDropdown.classList.contains('show')) {
                notificationDropdown.classList.remove('show');
            }
            
            // Toggle message popup
            messagePopup.classList.toggle('show');
            
            // Mark all messages as read when popup is opened
            if (messagePopup.classList.contains('show')) {
                // Hide message indicator
                if (messageIndicator) {
                    messageIndicator.style.display = 'none';
                }
                
                // Mark only unread messages as read
                document.querySelectorAll(".message-item.message:not(.read)").forEach(message => {
                    markMessageAsRead(message);
                });
            }
        });
        
        // Close message popup when clicking outside
        document.addEventListener('click', event => {
            if (messagePopup && 
                !messageToggleBtn.contains(event.target) && 
                messagePopup.classList.contains('show')) {
                messagePopup.classList.remove('show');
            }
        });
    }
    
    // Close notification dropdown when clicking outside
    document.addEventListener('click', event => {
        if (notificationDropdown && 
            !notificationToggleBtn.contains(event.target) && 
            notificationDropdown.classList.contains('show')) {
            notificationDropdown.classList.remove('show');
        }
    });
});

// Websocket message handler
document.body.addEventListener('htmx:wsAfterMessage', function(event) {
    // Show notification indicator for any message
    const notificationDot = document.getElementById('notification-indicator');
    if (notificationDot) {
        notificationDot.style.display = 'block';
    }
    
    // Remove "no notifications" message if it exists
    const noNotificationsMsg = document.getElementById('no-notifications-message');
    if (noNotificationsMsg) {
        noNotificationsMsg.remove();
    }
    
    // Add the new notification to the container
    if (event.detail.message) {
        const container = document.getElementById('notifications-container');
        if (container) {
            container.insertAdjacentHTML('afterbegin', event.detail.message);
        }
    }
});