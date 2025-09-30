document.addEventListener("DOMContentLoaded", function () {
  const burgerMenu = document.getElementById("burger-menu");
  const mobileMenu = document.getElementById("mobile-menu");
  const mobileNotificationsBtn = document.getElementById(
    "dropdownMenuButtonMobile"
  );
  const mobileMessagesBtn = document.getElementById(
    "messageDropdownButtonMobile"
  );
  const mobileNotificationsOverlay = document.getElementById(
    "mobile-notifications-overlay"
  );
  const mobileMessagesOverlay = document.getElementById(
    "mobile-messages-overlay"
  );
  const closeMobileNotifications = document.getElementById(
    "close-mobile-notifications"
  );
  const closeMobileMessages = document.getElementById("close-mobile-messages");

  // Burger menu functionality
  if (burgerMenu && mobileMenu) {
    burgerMenu.addEventListener("click", function (event) {
      event.stopPropagation();
      burgerMenu.classList.toggle("active");
      mobileMenu.classList.toggle("active");
    });

    mobileMenu.addEventListener("click", function (event) {
      event.stopPropagation();
    });

    // Close menu when clicking outside
    document.addEventListener("click", function (event) {
      if (
        !burgerMenu.contains(event.target) &&
        !mobileMenu.contains(event.target)
      ) {
        burgerMenu.classList.remove("active");
        mobileMenu.classList.remove("active");
      }
    });

    // Close menu when clicking on nav links
    const navLinks = mobileMenu.querySelectorAll(".nav-icon");
    navLinks.forEach((link) => {
      link.addEventListener("click", function (e) {
        // Don't close menu for notifications and messages
        if (
          !link.classList.contains("notification-wrapper") &&
          !link.classList.contains("message-wrapper")
        ) {
          burgerMenu.classList.remove("active");
          mobileMenu.classList.remove("active");
        }
      });
    });
  }

  // Mobile notifications full-screen
  if (mobileNotificationsBtn && mobileNotificationsOverlay) {
    mobileNotificationsBtn.addEventListener("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      mobileNotificationsOverlay.classList.add("active");
      // Close mobile menu
      burgerMenu.classList.remove("active");
      mobileMenu.classList.remove("active");
      // Prevent body scroll
      document.body.style.overflow = "hidden";
    });
  }

  // Mobile messages full-screen
  if (mobileMessagesBtn && mobileMessagesOverlay) {
    mobileMessagesBtn.addEventListener("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      mobileMessagesOverlay.classList.add("active");
      // Close mobile menu
      burgerMenu.classList.remove("active");
      mobileMenu.classList.remove("active");
      // Prevent body scroll
      document.body.style.overflow = "hidden";
    });
  }

  // Close mobile notifications
  if (closeMobileNotifications) {
    closeMobileNotifications.addEventListener("click", function () {
      mobileNotificationsOverlay.classList.remove("active");
      document.body.style.overflow = "";
    });
  }

  // Close mobile messages
  if (closeMobileMessages) {
    closeMobileMessages.addEventListener("click", function () {
      mobileMessagesOverlay.classList.remove("active");
      document.body.style.overflow = "";
    });
  }

  // Close overlays when clicking outside content
  [mobileNotificationsOverlay, mobileMessagesOverlay].forEach((overlay) => {
    if (overlay) {
      overlay.addEventListener("click", function (e) {
        if (e.target === overlay) {
          overlay.classList.remove("active");
          document.body.style.overflow = "";
        }
      });
    }
  });

  // Close overlays on escape key
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      if (
        mobileNotificationsOverlay &&
        mobileNotificationsOverlay.classList.contains("active")
      ) {
        mobileNotificationsOverlay.classList.remove("active");
        document.body.style.overflow = "";
      }
      if (
        mobileMessagesOverlay &&
        mobileMessagesOverlay.classList.contains("active")
      ) {
        mobileMessagesOverlay.classList.remove("active");
        document.body.style.overflow = "";
      }
    }
  });
});
