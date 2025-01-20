(function() {
  "use strict";

  // Make cardClick globally available
  window.cardClick = function(event, teacherUrl) {
    console.log("Clicked teacher URL:", teacherUrl);
    try {
        if (!window.getSelection().toString()) {
            // Redirect to the provided URL
            window.location.href = teacherUrl;
        }
    } catch (error) {
        console.error("Error in cardClick:", error);
    }
 };

  function toggleScrolled() {
    const selectBody = document.querySelector('body');
    const selectHeader = document.querySelector('#header');
    if (!selectHeader.classList.contains('scroll-up-sticky') && 
        !selectHeader.classList.contains('sticky-top') && 
        !selectHeader.classList.contains('fixed-top')) return;
    window.scrollY > 100 ? selectBody.classList.add('scrolled') : selectBody.classList.remove('scrolled');
  }
  document.addEventListener('scroll', toggleScrolled);
  window.addEventListener('load', toggleScrolled);

  const mobileNavToggleBtn = document.querySelector('.mobile-nav-toggle');
  // Add null check before using mobileNavToggleBtn
  if (mobileNavToggleBtn) {
    function mobileNavToogle() {
      document.querySelector('body').classList.toggle('mobile-nav-active');
      mobileNavToggleBtn.classList.toggle('bi-list');
      mobileNavToggleBtn.classList.toggle('bi-x');
    }
    mobileNavToggleBtn.addEventListener('click', mobileNavToogle);
  }

  document.querySelectorAll('#navmenu a').forEach(navmenu => {
    navmenu.addEventListener('click', () => {
      if (document.querySelector('.mobile-nav-active')) {
        mobileNavToogle();
      }
    });
  });

  // Tab switching functionality
  const initTabs = () => {
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');

    if (!tabButtons.length) return;

    tabButtons.forEach(button => {
      button.addEventListener('click', () => {
        const tabId = button.getAttribute('data-tab');
        
        // Remove active class from all buttons and hide contents
        tabButtons.forEach(btn => btn.classList.remove('active'));
        tabContents.forEach(content => content.style.display = 'none');
        
        // Add active class to clicked button and show content
        button.classList.add('active');
        const targetContent = document.getElementById(tabId);
        if (targetContent) {
          targetContent.style.display = 'block';
        }
      });
    });

    // Show first tab by default
    const firstTab = tabButtons[0];
    if (firstTab) {
      firstTab.click();
    }
  };

  // Initialize tabs when DOM is loaded
  document.addEventListener('DOMContentLoaded', initTabs);
})();