(function() {
  "use strict";

  window.toggleFilters = function() {
    const filterPanel = document.getElementById('filterPanel');
    filterPanel.classList.toggle('active');
  };

  // Initialize when DOM loads
  document.addEventListener('DOMContentLoaded', () => {
    // Close popup on escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        closeTeacherPopup();
      }
    });

    // Filter panel click outside
    document.addEventListener('click', (e) => {
      const filterPanel = document.getElementById('filterPanel');
      const filterBtn = document.querySelector('.filter-btn');
      
      if (filterPanel && filterBtn && 
          !filterPanel.contains(e.target) && 
          !filterBtn.contains(e.target) && 
          filterPanel.classList.contains('active')) {
        toggleFilters();
      }
    });

    // Handle escape key for filter panel
    document.addEventListener('keydown', (e) => {
      const filterPanel = document.getElementById('filterPanel');
      if (e.key === 'Escape' && filterPanel && filterPanel.classList.contains('active')) {
        toggleFilters();
      }
    });

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
  });
})();
