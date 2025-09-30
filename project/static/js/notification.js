
let csrfToken = '';
const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
if (csrfInput) {
    csrfToken = csrfInput.value;
}

function markItemAsRead(el) {
    if (!el || el.classList.contains('read')) return;
    const id = el.dataset.id;
    if (!id) return;

    fetch(`/notifications/read/${id}/`, {
        method: "POST",
        headers: {
            "X-CSRFToken": csrfToken,
            "Content-Type": "application/json"
        }
    })
    .then(resp => {
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return resp.json();
    })
    .then(data => {
        if (data.is_read) {
            el.classList.add('read');
        }
    })
    .catch(err => console.error(`Error marking ${id} as read:`, err));
}

/** Mark all unread, given a NodeList or selector */
function markAllUnreadIn(target) {
    const list = (typeof target === 'string')
        ? document.querySelectorAll(target)
        : target;
    if (!list) return;
    list.forEach(el => markItemAsRead(el));
}

document.addEventListener('DOMContentLoaded', () => {
    // Desktop controls
    const notificationToggleBtn = document.getElementById('dropdownMenuButton');
    const notificationDropdown  = document.getElementById('notification-list');
    const notificationDot       = document.getElementById('notification-indicator');

    const messageToggleBtn = document.getElementById('messageDropdownButton');
    const messagePopup     = document.getElementById('message-popup');
    const messageIndicator = document.getElementById('message-indicator');

    // Mobile controls
    const mobileNotificationsBtn     = document.getElementById('dropdownMenuButtonMobile');
    const mobileMessagesBtn          = document.getElementById('messageDropdownButtonMobile');
    const mobileNotificationsOverlay = document.getElementById('mobile-notifications-overlay');
    const mobileMessagesOverlay      = document.getElementById('mobile-messages-overlay');
    const mobileNotifIndicator       = document.getElementById('notification-indicator-mobile');
    const mobileMsgIndicator         = document.getElementById('message-indicator-mobile');

    // ===== Desktop: Notifications dropdown
    if (notificationToggleBtn && notificationDropdown) {
        notificationToggleBtn.addEventListener('click', event => {
            event.preventDefault();

            // Close messages popup if open
            if (messagePopup && messagePopup.classList.contains('show')) {
                messagePopup.classList.remove('show');
            }

            // Toggle dropdown
            notificationDropdown.classList.toggle('show');

            if (notificationDropdown.classList.contains('show')) {
                // Hide bell dot
                if (notificationDot) notificationDot.style.display = 'none';
                // Mark notifications as read (desktop list items expected to have .notification-item)
                markAllUnreadIn('#notification-list .notification-item:not(.read)');
            }
        });
    }

    // ===== Desktop: Messages popup
    if (messageToggleBtn && messagePopup) {
        messageToggleBtn.addEventListener('click', event => {
            event.preventDefault();

            // Close notifications dropdown if open
            if (notificationDropdown && notificationDropdown.classList.contains('show')) {
                notificationDropdown.classList.remove('show');
            }

            // Toggle message popup
            messagePopup.classList.toggle('show');

            if (messagePopup.classList.contains('show')) {
                // Hide counter badge
                if (messageIndicator) messageIndicator.style.display = 'none';
                // Mark desktop messages as read
                markAllUnreadIn('.message-item.message:not(.read)');
            }
        });
    }

    // --- Do not close dropdowns when rejection modal is open
    document.addEventListener('click', event => {
        const rejectionModal = document.getElementById('rejectionReasonModal');
        if (rejectionModal && rejectionModal.style.display === 'flex') return;

        if (notificationDropdown &&
            !notificationToggleBtn.contains(event.target) &&
            notificationDropdown.classList.contains('show')) {
            notificationDropdown.classList.remove('show');
        }
        if (messagePopup &&
            !messageToggleBtn.contains(event.target) &&
            !messagePopup.contains(event.target) &&
            messagePopup.classList.contains('show')) {
            messagePopup.classList.remove('show');
        }
    });

    // ===== Mobile: when opening full-screen overlays, mark as read
    if (mobileMessagesBtn && mobileMessagesOverlay) {
        mobileMessagesBtn.addEventListener('click', e => {
            // Overlay opening is handled in header.html inline script.
            // Here we just schedule marking as read slightly later to ensure DOM is ready.
            setTimeout(() => {
                if (mobileMsgIndicator) mobileMsgIndicator.style.display = 'none';
                markAllUnreadIn('#mobile-messages-content .mobile-message-item:not(.read)');
            }, 0);
        });

        // Also mark a single message immediately on tap inside mobile overlay
        mobileMessagesOverlay.addEventListener('click', e => {
            const item = e.target.closest('.mobile-message-item');
            if (item) markItemAsRead(item);
        });
    }

    if (mobileNotificationsBtn && mobileNotificationsOverlay) {
        mobileNotificationsBtn.addEventListener('click', e => {
            // Even if the mobile notifications list is rendered elsewhere,
            // we can still mark desktop list items so the backend flips state.
            setTimeout(() => {
                if (mobileNotifIndicator) mobileNotifIndicator.style.display = 'none';
                // Try mobile overlay first, then desktop dropdown as a fallback.
                markAllUnreadIn('#mobile-notifications-content .mobile-notification-item:not(.read)');
                markAllUnreadIn('#notification-list .notification-item:not(.read)');
            }, 0);
        });

        mobileNotificationsOverlay.addEventListener('click', e => {
            const item = e.target.closest('.mobile-notification-item');
            if (item) markItemAsRead(item);
        });
    }

    // ===== Optional: mark as read when an item actually becomes visible (helps on small screens)
    const visibilityObserver = ('IntersectionObserver' in window)
        ? new IntersectionObserver(entries => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    markItemAsRead(entry.target);
                    visibilityObserver.unobserve(entry.target);
                }
            });
        }, { root: null, threshold: 0.4 })
        : null;

    if (visibilityObserver) {
        document.querySelectorAll('.message-item.message:not(.read), #notification-list .notification-item:not(.read), #mobile-messages-content .mobile-message-item:not(.read), #mobile-notifications-content .mobile-notification-item:not(.read)')
            .forEach(el => visibilityObserver.observe(el));
    }

});

// Websocket push: show indicator + drop item into list
document.body.addEventListener('htmx:wsAfterMessage', function(event) {
    // Show indicators
    const notificationDot = document.getElementById('notification-indicator');
    const mobileNotifIndicator = document.getElementById('notification-indicator-mobile');
    if (notificationDot) notificationDot.style.display = 'block';
    if (mobileNotifIndicator) mobileNotifIndicator.style.display = 'block';

    // Remove "no notifications" message if exists (desktop)
    const noNotificationsMsg = document.getElementById('no-notifications-message');
    if (noNotificationsMsg) noNotificationsMsg.remove();

    // Add the new notification HTML (server-sent) to a container if possible
    if (event.detail.message) {
        const container =
            document.getElementById('notifications-container') ||
            document.getElementById('notification-list');
        if (container) {
            container.insertAdjacentHTML('afterbegin', event.detail.message);
        }
    }
});


// ===== Rejection reason modal controls (keep as-is)
const rejectionModal = document.getElementById('rejectionReasonModal');
const rejectionTextElement = document.getElementById('rejectionReasonText');

function closeRejectionModal() {
    if (rejectionModal) {
        rejectionModal.style.display = 'none';
    }
}

document.addEventListener('click', function(event) {
    const reasonButton = event.target.closest('.view-rejection-reason-btn');

    if (reasonButton) {
        event.preventDefault();
        event.stopPropagation();

        const reason = reasonButton.dataset.reason;

        if (rejectionTextElement && rejectionModal) {
            rejectionTextElement.textContent = reason;
            rejectionModal.style.display = 'flex';
        }
        return false;
    }

    if (event.target === rejectionModal) {
        closeRejectionModal();
    }
});

document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        closeRejectionModal();
    }
});
