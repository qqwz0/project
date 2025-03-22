(function() {
  "use strict";
  // Initialize when DOM loads
  document.addEventListener('DOMContentLoaded', () => {
    // Close popup on escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        closeTeacherPopup();
      }
    });

    // Simplified scroll handler
    function handleScroll() {
      const header = document.getElementById('header');
      if (!header) return;
      
      if (window.scrollY > 20) {
        header.classList.add('scrolled-header');
      } else {
        header.classList.remove('scrolled-header');
      }
    }
    
    document.addEventListener('scroll', handleScroll);
    window.addEventListener('load', handleScroll);
  });
})();