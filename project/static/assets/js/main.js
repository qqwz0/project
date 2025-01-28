(function() {
  "use strict";

  window.toggleFilters = function() {
    const filterPanel = document.getElementById('filterPanel');
    filterPanel.classList.toggle('active');
  };

  window.openTeacherPopup = function(event, button) {
    event.stopPropagation();
    try {
      const popup = document.getElementById('teacherPopup');
      if (popup) {
        // Update popup content with data attributes
        document.getElementById('popupPhoto').src = button.dataset.teacherPhoto;
        document.getElementById('popupName').textContent = button.dataset.teacherName;
        document.getElementById('popupPosition').textContent = button.dataset.teacherPosition;
        document.getElementById('popupDepartment').textContent = button.dataset.teacherDepartment;

        // Handle slots data
        const slotsContainer = document.getElementById('popupSlots');
        if (button.dataset.teacherSlots === 'multiple') {
          const slotsData = JSON.parse(button.dataset.slotsData);
          slotsContainer.innerHTML = `
            <p><strong>Загальна кількість місць:</strong></p>
            <ul>
              ${slotsData.map(slot => 
                `<li><strong>${slot.stream_id.stream_code}: </strong>${slot.available_slots}</li>`
              ).join('')}
            </ul>`;
        } else {
          const slotData = JSON.parse(button.dataset.slotsData);
          slotsContainer.innerHTML = `<p><strong>Місця:</strong> ${slotData.available_slots}</p>`;
        }

        popup.style.display = 'block';
        document.body.style.overflow = 'hidden';
      }
    } catch (error) {
      console.error("Error opening popup:", error);
    }
  };

  window.closeTeacherPopup = function() {
    try {
      const popup = document.getElementById('teacherPopup');
      if (popup) {
        popup.style.display = 'none';
        document.body.style.overflow = 'auto';
      }
    } catch (error) {
      console.error("Error closing popup:", error);
    }
  };

  // Initialize when DOM loads
  document.addEventListener('DOMContentLoaded', () => {
    // Close popup on escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        closeTeacherPopup();
      }
    });

    // Close popup when clicking outside
    document.addEventListener('click', (e) => {
      const popup = document.getElementById('teacherPopup');
      if (popup && e.target === popup) {
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