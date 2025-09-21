/* Власна система підказок замість Intro.js */
(function() {
  'use strict';

  var currentTour = null;
  var currentStep = 0;
  var tourSteps = [];
  var overlay = null;
  var highlight = null;
  var tooltip = null;

  function createElement(tag, className, innerHTML) {
    var el = document.createElement(tag);
    if (className) el.className = className;
    if (innerHTML) el.innerHTML = innerHTML;
    return el;
  }

  function getElementPosition(element) {
    var rect = element.getBoundingClientRect();
    return {
      top: rect.top + window.scrollY,
      left: rect.left + window.scrollX,
      width: rect.width,
      height: rect.height
    };
  }

  function getOptimalPosition(element, tooltipWidth, tooltipHeight) {
    var rect = element.getBoundingClientRect();
    var viewport = {
      width: window.innerWidth,
      height: window.innerHeight
    };
    
    var margin = 15; // менший відступ для кращого позиціонування
    var spaceBelow = viewport.height - rect.bottom - margin;
    var spaceAbove = rect.top - margin;
    var spaceRight = viewport.width - rect.right - margin;
    var spaceLeft = rect.left - margin;
    
    // Спеціальна логіка для конкретних елементів
    if (element.classList.contains('segment-switcher')) {
      // На мобільних - завжди знизу для перемикача
      if (window.innerWidth <= 640) {
        if (spaceBelow >= tooltipHeight) return 'bottom';
        if (spaceAbove >= tooltipHeight) return 'top';
        return 'bottom';
      }
      // На десктопі - праворуч
      if (spaceRight >= tooltipWidth) return 'right';
      if (spaceBelow >= tooltipHeight) return 'bottom';
      if (spaceAbove >= tooltipHeight) return 'top';
      return 'right';
    }
    
    if (element.classList.contains('filter-section') || element.classList.contains('mobile-filter-bar')) {
      // На мобільних - завжди знизу для фільтрів
      if (window.innerWidth <= 640) {
        if (spaceBelow >= tooltipHeight) return 'bottom';
        if (spaceAbove >= tooltipHeight) return 'top';
        return 'bottom';
      }
      // На десктопі - праворуч
      if (spaceRight >= tooltipWidth) return 'right';
      if (spaceBelow >= tooltipHeight) return 'bottom';
      if (spaceAbove >= tooltipHeight) return 'top';
      return 'right';
    }
    
    // Перевіряємо чи елемент в нижній частині екрану
    var isElementInBottomHalf = rect.top > viewport.height / 2;
    var isElementInTopHalf = rect.bottom < viewport.height / 2;
    
    // На мобільних пристроях - завжди праворуч
    if (window.innerWidth <= 640) {
      if (spaceRight >= tooltipWidth) return 'right';
      if (spaceBelow >= tooltipHeight) return 'bottom';
      if (spaceAbove >= tooltipHeight) return 'top';
      return 'right';
    }
    
    // На десктопі враховуємо всі позиції з пріоритетом ближчих
    if (isElementInBottomHalf && spaceAbove >= tooltipHeight) return 'top';
    if (isElementInTopHalf && spaceBelow >= tooltipHeight) return 'bottom';
    if (spaceBelow >= tooltipHeight) return 'bottom';
    if (spaceAbove >= tooltipHeight) return 'top';
    if (spaceRight >= tooltipWidth) return 'right';
    if (spaceLeft >= tooltipWidth) return 'left';
    
    return 'bottom';
  }

  function positionTooltip(element, tooltip, position) {
    var rect = element.getBoundingClientRect();
    var tooltipRect = tooltip.getBoundingClientRect();
    var margin = 8; // менший відступ для кращого позиціонування

    var top, left;

    // Спеціальна логіка для проблемних елементів - завжди показуємо зверху
    var isProblemElement = element.classList.contains('streams-label');
    
    // Спеціальна логіка для контейнера дій - праворуч
    var isActionsContainer = element.classList.contains('theme-actions');
    
    
    // Спеціальна логіка для елементів каталогу - завжди праворуч
    var isCatalogElement = element.classList.contains('segment-switcher') ||
                           element.classList.contains('filter-section') ||
                           element.classList.contains('mobile-filter-bar');
    
    // Спеціальна логіка для поля пошуку
    var isSearchElement = element.classList.contains('form-searching') ||
                          element.querySelector('input[type="text"]') ||
                          element.querySelector('input[placeholder*="Пошук"]');
    
    // Спеціальна логіка для кнопок дій - завжди праворуч
    var isActionButton = element.classList.contains('complete-button') ||
                         element.classList.contains('cancel-button') ||
                         element.classList.contains('file-upload-btn') ||
                         element.classList.contains('add-comment-btn') ||
                         element.classList.contains('action-btn');
    
    // Спеціальна логіка для кнопок зберегти та завершити
    var isSaveOrBackButton = element.classList.contains('save-button') ||
                             element.classList.contains('back-button');
    
    // Спеціальна логіка для заголовка управління темами
    var isThemesHeader = element.tagName === 'H3' && element.textContent.includes('Управління темами');
    
    
    // На мобільних пристроях - завжди центруємо всі підказки
    if (window.innerWidth <= 640) {
      // Визначаємо вертикальну позицію
      if (isProblemElement || isActionsContainer || isActionButton || isSaveOrBackButton || isThemesHeader) {
        // Для проблемних елементів, контейнера дій, кнопок дій, кнопок зберегти/завершити та заголовка тем - зверху
        // Більший відступ для кращого позиціонування
        var mobileMargin = isActionsContainer ? 15 : margin;
        top = rect.top - tooltipRect.height - mobileMargin;
      } else {
        // Для всіх інших - знизу
        top = rect.bottom + margin;
      }
      // Горизонтально - завжди по центру екрану
      left = window.innerWidth / 2;
    } else {
      // На десктопі - звичайна логіка
      if (isActionsContainer) {
        // Спеціальна логіка для контейнера дій - праворуч (пріоритет)
        top = rect.top + (rect.height / 2) - (tooltipRect.height / 2);
        left = rect.right + margin;
      } else if (isActionButton) {
        // Спеціальна логіка для кнопок дій - праворуч
        top = rect.top + (rect.height / 2) - (tooltipRect.height / 2);
        left = rect.right + margin;
      } else if (isSearchElement) {
        // Спеціальна логіка для поля пошуку - знизу, трохи правіше
        top = rect.bottom + margin;
        left = rect.left + (rect.width / 2) - (tooltipRect.width / 2) + 30;
      } else if (isCatalogElement) {
        // Спеціальна логіка для елементів каталогу - праворуч
        if (element.classList.contains('segment-switcher')) {
          // Для перемикача пошуку - ще нижче центру
          top = rect.top + (rect.height / 2) - (tooltipRect.height / 2) + 40;
          left = rect.right + margin;
        } else {
          // Для фільтрів - по центру
          top = rect.top + (rect.height / 2) - (tooltipRect.height / 2);
          left = rect.right + margin;
        }
      } else if (isProblemElement) {
        // Завжди показуємо зверху для цих елементів
        var margin = 8;
        top = rect.top - tooltipRect.height - margin;
        left = rect.left + (rect.width / 2) - (tooltipRect.width / 2);
      } else {
        // Звичайна логіка для інших елементів
        switch (position) {
          case 'top':
            top = rect.top - tooltipRect.height - margin;
            left = rect.left + (rect.width / 2) - (tooltipRect.width / 2);
            break;
          case 'bottom':
            top = rect.bottom + margin;
            left = rect.left + (rect.width / 2) - (tooltipRect.width / 2);
            break;
          case 'left':
            top = rect.top + (rect.height / 2) - (tooltipRect.height / 2);
            left = rect.left - tooltipRect.width - margin;
            break;
          case 'right':
            top = rect.top + (rect.height / 2) - (tooltipRect.height / 2);
            left = rect.right + margin;
            break;
          default: // bottom
            top = rect.bottom + margin;
            left = rect.left + (rect.width / 2) - (tooltipRect.width / 2);
            break;
        }
      }
    }

    // Перевірка меж екрану з більш точними обмеженнями
    var viewportMargin = 10;
    if (top < viewportMargin) top = viewportMargin;
    if (top + tooltipRect.height > window.innerHeight - viewportMargin) {
      top = window.innerHeight - tooltipRect.height - viewportMargin;
    }
    
    // На мобільних пристроях - особлива логіка для центрування
    if (window.innerWidth <= 640) {
      // Центруємо по горизонталі - встановлюємо left як центр екрану
      // CSS transform: translateX(-50%) зробить правильне центрування
      left = window.innerWidth / 2;
    } else {
      // На десктопі - звичайна перевірка
      if (left < viewportMargin) left = viewportMargin;
      if (left + tooltipRect.width > window.innerWidth - viewportMargin) {
        left = window.innerWidth - tooltipRect.width - viewportMargin;
      }
    }

    tooltip.style.top = (top + window.scrollY) + 'px';
    tooltip.style.left = (left + window.scrollX) + 'px';
  }

  function createTooltip(step, stepIndex) {
    var tooltip = createElement('div', 'custom-tour-tooltip');
    
    // Спеціальний розмір для статусу
    var isStatusTooltip = step.title && step.title.includes('Активна/Неактивна');
    if (isStatusTooltip) {
      tooltip.style.maxWidth = '180px';
      tooltip.style.width = '180px';
    }
    
    var title = step.title ? '<div class="custom-tour-tooltip-title">' + step.title + '</div>' : '';
    var text = '<div class="custom-tour-tooltip-text">' + (step.intro || step.text || '') + '</div>';
    var button = '<button class="custom-tour-tooltip-button">Зрозуміло ></button>';
    var progress = '<div class="custom-tour-progress">' + (stepIndex + 1) + '/' + tourSteps.length + '</div>';
    
    tooltip.innerHTML = title + text + button + progress;
    
    // Додаємо обробник кнопки
    var buttonEl = tooltip.querySelector('.custom-tour-tooltip-button');
    if (buttonEl) {
      buttonEl.addEventListener('click', nextStep);
    }
    
    return tooltip;
  }

  function createHighlight(element) {
    var rect = element.getBoundingClientRect();
    
    var highlight = createElement('div', 'custom-tour-highlight');
    
    // Використовуємо getBoundingClientRect для точного позиціонування
    var padding = 8;
    
    // Спеціальна логіка для проблемних елементів
    var isProblemElement = element.classList.contains('status-indicator') || 
                           element.classList.contains('streams-label') ||
                           element.classList.contains('edit-btn') ||
                           element.classList.contains('requests-count');
    
    if (isProblemElement) {
      // Для проблемних елементів робимо highlight точно по розміру елемента
      var padding = element.classList.contains('status-indicator') ? 2 : 0; // невеликий padding для статусу
      highlight.style.top = (rect.top + window.scrollY - padding) + 'px';
      highlight.style.left = (rect.left + window.scrollX - padding) + 'px';
      highlight.style.width = (rect.width + padding * 2) + 'px';
      highlight.style.height = (rect.height + padding * 2) + 'px';
    } else {
      // Звичайна логіка з padding
      highlight.style.top = (rect.top + window.scrollY - padding) + 'px';
      highlight.style.left = (rect.left + window.scrollX - padding) + 'px';
      highlight.style.width = (rect.width + padding * 2) + 'px';
      highlight.style.height = (rect.height + padding * 2) + 'px';
    }
    
    // Не блокуємо кліки - залишаємо елемент клікабельним
    highlight.style.pointerEvents = 'none';
    
    // Примусово застосовуємо стилі для гарантії видимості
    highlight.style.display = 'block';
    highlight.style.visibility = 'visible';
    highlight.style.opacity = '1';
    highlight.style.border = '3px solid #1d4ed8';
    highlight.style.borderRadius = '12px';
    highlight.style.background = 'transparent';
    highlight.style.zIndex = '999998';
    
    return highlight;
  }

  function showStep(stepIndex) {
    if (stepIndex >= tourSteps.length) {
      endTour();
      return;
    }
    
    var step = tourSteps[stepIndex];
    var element = typeof step.element === 'string' ? 
      document.querySelector(step.element) : step.element;
    
    if (!element) {
      showStep(stepIndex + 1);
      return;
    }
    
    // Автоматично переходимо на потрібну вкладку (тільки на поточній сторінці)
    autoSwitchToElement(element);
    
    // Автоматично прокручуємо до елемента, якщо він не в видимій області
    var rect = element.getBoundingClientRect();
    var viewportHeight = window.innerHeight;
    var viewportWidth = window.innerWidth;
    
    // Перевіряємо, чи елемент в видимій області
    var isVisible = rect.top >= 0 && rect.bottom <= viewportHeight && 
                   rect.left >= 0 && rect.right <= viewportWidth;
    
    if (!isVisible) {
      element.scrollIntoView({ 
        behavior: 'smooth', 
        block: 'center', 
        inline: 'center' 
      });
      
      // Чекаємо трохи, щоб прокрутка завершилася
      setTimeout(function() {
        showStep(stepIndex);
      }, 500);
      return;
    }
    
    // Створюємо підсвічування
    if (highlight) highlight.remove();
    highlight = createHighlight(element);
    document.body.appendChild(highlight);
    
    // Створюємо підказку
    if (tooltip) tooltip.remove();
    tooltip = createTooltip(step, stepIndex);
    document.body.appendChild(tooltip);
    
    // Позиціонуємо підказку
    var position = getOptimalPosition(element, 220, 120); // менші розміри
    
    // Спеціальна логіка для контейнера дій та кнопок дій - завжди праворуч
    var isActionsContainer = element.classList.contains('theme-actions');
    var isActionButton = element.classList.contains('action-btn') ||
                         element.classList.contains('complete-button') ||
                         element.classList.contains('cancel-button') ||
                         element.classList.contains('file-upload-btn') ||
                         element.classList.contains('add-comment-btn');
    
    // Спеціальна логіка для кнопок зберегти та завершити
    var isSaveOrBackButton = element.classList.contains('save-button') ||
                             element.classList.contains('back-button');
    
    // Спеціальна логіка для заголовка управління темами
    var isThemesHeader = element.tagName === 'H3' && element.textContent.includes('Управління темами');
    
    
    if (isActionsContainer || isActionButton) {
      position = 'right';
    } else if (window.innerWidth <= 640) {
      // На мобільних пристроях - використовуємо 'top' для спеціальних елементів, 'bottom' для інших
      if (isActionsContainer || isActionButton || isSaveOrBackButton || isThemesHeader) {
        position = 'top';
      } else {
        position = 'bottom';
      }
    }
    
    tooltip.classList.add('position-' + position);
    positionTooltip(element, tooltip, position);
    
    currentStep = stepIndex;
  }

  function nextStep() {
    // Автоматично переходимо на потрібну вкладку перед наступним кроком
    var nextStepIndex = currentStep + 1;
    if (nextStepIndex < tourSteps.length) {
      var nextStep = tourSteps[nextStepIndex];
      var nextElement = typeof nextStep.element === 'string' ? 
        document.querySelector(nextStep.element) : nextStep.element;
      
      if (nextElement) {
        autoSwitchToElement(nextElement);
      }
    }
    
    showStep(nextStepIndex);
  }

  function autoSwitchToElement(element) {
    // Перевіряємо чи це сторінка редагування профіля
    var isEditProfilePage = document.querySelector('.edit-profile-container');
    
    if (isEditProfilePage) {
      // На сторінці редагування профіля прокручуємо до елемента
      setTimeout(function() {
        element.scrollIntoView({
          behavior: 'smooth',
          block: 'center',
          inline: 'nearest'
        });
      }, 100);
      return;
    }
    
    // Перевіряємо чи елемент знаходиться в секції з вкладками на поточній сторінці
    var sectionElement = element.closest('#active-section, #pending-section, #archive-section, #requests-section, #info-section');
    
    if (sectionElement) {
      var sectionId = sectionElement.id;
      
      var tabMap = {
        'active-section': 'active',
        'pending-section': 'requests', 
        'archive-section': 'archive',
        'requests-section': 'requests',
        'info-section': 'info'
      };
      
      var tabId = tabMap[sectionId];
      
      if (tabId) {
        var tabButton = document.querySelector('.tab[data-tab="' + tabId + '"]');
        
        if (tabButton && !tabButton.classList.contains('active')) {
          // Використовуємо функцію loadTab якщо вона існує, інакше клікаємо
          if (typeof window.loadTab === 'function') {
            window.loadTab(tabId, tabButton);
          } else {
            // Альтернативний спосіб перемикання вкладок
            document.querySelectorAll('.tab').forEach(function(t) {
              t.classList.remove('active');
            });
            tabButton.classList.add('active');
            
            // Показуємо відповідний контент
            document.querySelectorAll('.tab-content').forEach(function(el) {
              el.style.display = 'none';
            });
            var targetSection = document.getElementById(tabId + '-section');
            if (targetSection) {
              targetSection.style.display = 'block';
            }
          }
          // Чекаємо трохи щоб вкладка встигла перемкнутися
          setTimeout(function() {
            scrollToElementInContainer(element);
          }, 200);
          return;
        }
      }
    }
    
    // Прокручуємо до елемента в поточному контейнері
    scrollToElementInContainer(element);
  }

  function scrollToElementInContainer(element) {
    // Прокручуємо скролбари всередині контейнерів
    var scrollableContainers = element.closest('.files-scroll-container, .scroll-container, .content-scroll, .tab-content, .form-content, .edit-profile-container');
    if (scrollableContainers) {
      var containerRect = scrollableContainers.getBoundingClientRect();
      var elementRect = element.getBoundingClientRect();
      
      // Перевіряємо чи елемент видимий в контейнері
      if (elementRect.top < containerRect.top || elementRect.bottom > containerRect.bottom) {
        element.scrollIntoView({
          behavior: 'smooth',
          block: 'center',
          inline: 'nearest'
        });
      }
    } else {
      // Якщо немає скролованого контейнера, просто прокручуємо до елемента
      element.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
        inline: 'nearest'
      });
    }
  }

  function endTour() {
    if (overlay) overlay.remove();
    if (highlight) highlight.remove();
    if (tooltip) tooltip.remove();
    
    overlay = null;
    highlight = null;
    tooltip = null;
    currentStep = 0;
    tourSteps = [];
    currentTour = null;
  }

  function startCustomTour(steps) {
    // Закриваємо попередній тур якщо він є
    endTour();
    
    tourSteps = steps;
    currentStep = 0;
    
    // Створюємо оверлей
    overlay = createElement('div', 'custom-tour-overlay');
    overlay.addEventListener('click', endTour);
    document.body.appendChild(overlay);
    
    // Завантажуємо CSS якщо потрібно
    if (!document.querySelector('link[href*="custom_tour.css"]')) {
      var link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = '/static/css/custom_tour.css';
      document.head.appendChild(link);
    }
    
    // Показуємо перший крок
    setTimeout(function() {
      showStep(0);
    }, 100);
  }

  // Експортуємо функцію
  window.startCustomTour = startCustomTour;
  window.endCustomTour = endTour;

})();
