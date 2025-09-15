/* Role- and page-aware Intro.js tour */
(function () {
  function isCatalogPage() {
    return !!document.querySelector('.main-container-catalog');
  }

  function isProfilePage() {
    return !!document.querySelector('.profile-container');
  }

  function isEditProfilePage() {
    return !!document.querySelector('.edit-profile-container');
  }

  function isCatalogPage() {
    return !!document.querySelector('.main-container-catalog');
  }

  function isHomePage() {
    return !!document.querySelector('.main-content .section-header .section-title');
  }

  function defined(element) {
    return !!element;
  }

  function safeStep(selector, intro) {
    var el = typeof selector === 'string' ? pickBestElement(selector) : selector;
    return el ? { element: el, intro: intro } : null;
  }

  function safeStepPos(selector, intro, position, offsetY, offsetX, mobileTop = false) {
    var el = typeof selector === 'string' ? pickBestElement(selector) : selector;
    if (!el) return null;
    var step = { element: el, intro: intro, position: position, _strict: true };
    if (offsetY !== undefined) step.offsetY = offsetY;
    if (offsetX !== undefined) step.offsetX = offsetX;
    if (mobileTop) step.mobileTop = mobileTop;
    return step;
  }

  function getBoundaryRect() {
    var boundary = document.querySelector('.profile-container') ||
                   document.querySelector('.edit-profile-container') ||
                   document.querySelector('.main-container-catalog') ||
                   document.querySelector('.search-results') ||
                   document.querySelector('main.profile-main') ||
                   document.body;
    return boundary.getBoundingClientRect();
  }

  // Choose the most relevant element for a selector: visible and closest to container center
  function pickBestElement(selector) {
    try {
      var list = Array.prototype.slice.call(document.querySelectorAll(selector));
      if (!list.length) return null;
      var b = getBoundaryRect();
      var cx = (b.left + b.right) / 2;
      var cy = (b.top + b.bottom) / 2;
      var best = null;
      var bestScore = Infinity;
      list.forEach(function (el) {
        var r = el.getBoundingClientRect();
        var visible = r.width > 0 && r.height > 0 && (r.bottom > b.top) && (r.top < b.bottom) && (r.right > b.left) && (r.left < b.right);
        if (!visible) return;
        var dx = (r.left + r.right) / 2 - cx;
        var dy = (r.top + r.bottom) / 2 - cy;
        var score = dx * dx + dy * dy; // distance squared to center
        if (score < bestScore) { bestScore = score; best = el; }
      });
      return best || list[0];
    } catch (_) { return document.querySelector(selector); }
  }

  function getCommonHeaderSteps() {
    return [
      safeStep('#nav-home', 'Головна: Сторінка з важливою інформацією. Дедлайни, оголошення та структура курсової роботи.'),
      safeStep('#nav-search', 'Каталог викладачів: Тут Ви можете знайти викладача чи тему для курсової роботи.'),
      safeStepPos('#dropdownMenuButton, #messageDropdownButton', "Сповіщення та повідомлення: Слідкуйте за листами, оголошеннями та статусом робіт.", 'left', 0, -100),
    ].filter(Boolean);
  }

  // Header steps for Home and Catalog pages
  function getHeaderNavSteps(isStudent) {
    return [
      safeStep('#nav-home', 'Головна: перехід на стартову сторінку із важливою інформацією.', 'bottom'),
      isStudent ? safeStep('#nav-search', 'Каталог викладачів: знайдіть викладача або тему для співпраці.', 'bottom') : null,
      safeStepPos('#dropdownMenuButton, #messageDropdownButton', "Сповіщення та повідомлення: тут з'являються нові події, оновлення та приватні повідомлення.", 'left', 0, -120),
    ].filter(Boolean);
  }

  // STUDENT page-specific steps
  function getStudentCatalogSteps() {
    return [
      safeStepPos('.search-section .form-searching', 'Пошук викладача або теми. Введіть запит та натисніть Enter.', 'bottom'),
      safeStepPos('.segment-switcher', 'Перемикач режимів пошуку: Шукайте окремо викладачів, теми або все разом.', 'bottom'),
      safeStepPos('.filter-section, .mobile-filter-bar', 'Фільтри: Кафедра, кількість місць, посада. Застосуйте потрібні фільтри для швидшого пошуку.', 'right'),
      safeStepPos('.teachers-list, .unified-results, .catalog-container, .themes-list, .all-content, .search-results, .results-section', 'Результати: Клікніть на викладача, щоб перейти до його профілю для детальнішої інформації. Натисніть синю стрілочку на картці для надсилання запиту.', 'bottom'),
    ].filter(Boolean);
  }

  function getStudentProfileSteps() {
    var steps = [];
    // 1. Запити
    steps.push(safeStep('.tabs .tab[data-tab="requests"]', 'Вкладка Запити: Відслідковуйте статус надісланих Вами запитів до викладачів.'));
    // 2. Активні
    steps.push(safeStep('.tabs .tab[data-tab="active"]', 'Вкладка Активні: Все про актуальну роботу.'));
    steps.push(safeStep('#active-section .files-scroll-container', 'Файли поточної роботи: Переглядайте та завантажуйте матеріали, тримайте зв\'язок з викладачем.'));
    steps.push(safeStep('#active-section .file-upload-form .file-input-label, #active-section .file-upload-btn', 'Додайте файл до активної роботи.'));
    // 3. Архів
    steps.push(safeStep('.tabs .tab[data-tab="archive"]', 'Вкладка Архів: Переглядайте завершені роботи та виставлені викладачем бали за них.'));
    // 4. Редагування
    steps.push(safeStep('.profile-buttons a[href*="edit"], .profile-buttons i.fa-edit', 'Редагування профілю: За потреби змініть контактні дані чи фото профіля.'));
    return steps.filter(Boolean);
  }

  function getStudentHomeSteps() {
    return [
      safeStep('#nav-home', 'Головна: тут зібрані важливі оголошення та матеріали.'),
      safeStep('.section-title', 'Актуальна інформація: слідкуйте за дедлайнами та оновленнями.'),
    ].filter(Boolean);
  }

  // TEACHER page-specific steps
  function getTeacherProfileSteps() {
    var steps = [];
    // 0. Редагування профілю — одразу після підказок хедера
    steps.push(safeStep('.profile-buttons a[href*="edit"], .profile-buttons i.fa-edit', 'Редагування профілю: змініть контактні дані, фото та іншу інформацію.'));
    // 1. Інформація
    steps.push(safeStep('.tabs .tab[data-tab="info"]', 'Інформація: Перелік Ваших тем та слотів для окремих потоків.'));
    steps.push(safeStep('.add-theme, .add-theme-btn', 'Додайте нову тему для студентів.'));
    // 2. Запити
    steps.push(safeStep('.tabs .tab[data-tab="requests"]', 'Запити: Керуйте надісланими запитами студентів.'));
    steps.push(safeStep('.pending-section .request-button.accept', 'Прийняти запит студента: прийміть запит, попередньо обравши тему з Вашого переліку чи з запропонованих студентом.'));
    steps.push(safeStep('.pending-section .request-button.reject', 'Відхилити запит: вкажіть причину відмови та відхиліть запит студента.'));
    // 3. Активні
    steps.push(safeStep('.tabs .tab[data-tab="active"]', 'Активні: Перегляньте актуальні роботи зі студентами.'));
    steps.push(safeStep('#active-section .edit-theme-btn', 'За потреби можна відредагувати тему активної роботи.'));
    steps.push(safeStep('#active-section .file-upload-form .file-input-label, #active-section .file-upload-btn', 'Надішліть файл стосовно активної роботи.'));
    steps.push(safeStep('#active-section .comment-textarea, #active-section .add-comment-btn', 'Лишайте фідбек та листуйтеся зі студентом.'));
    steps.push(safeStepPos('#active-section .complete-button', 'Завершити роботу: дозволяє виставити оцінку та перемістити роботу в архів.', 'right'));
    steps.push(safeStepPos('#active-section .cancel-button', 'Скасувати роботу: у тому випадку, якщо прийняли запит помилково.', 'right'));
    // 4. Архів
    steps.push(safeStep('.tabs .tab[data-tab="archive"]', 'Архів: завершені роботи з детальною інформацією та переліком надісланих файлів до них.'));
    return steps.filter(Boolean);
  }

  // EDIT PROFILE page core steps (common)
  function getEditProfileSteps() {
    var steps = [];
    steps.push(safeStep('.edit-profile-header .profile-image img, .edit-profile-header img#profile-preview', 'Фото профілю: за потреби оновіть аватар.'));
    steps.push(safeStep('.edit-form .personal-info, .personal-info', 'Особиста інформація: Можливість редагувати чи додавати основні дані.'));
    steps.push(safeStep('.edit-form .contacts, .contacts', 'Контакти: Додайте робочі контакти для зв\'язку.'));
    steps.push(safeStepPos('.save-button', 'Зберегти: Збережіть щойно зроблені зміни профілю.', 'right', 0, 0, true));
    steps.push(safeStepPos('.back-button', 'Завершити: Повернутися до сторінки профілю після збереження змін.', 'right', 0, 0, true));
    return steps.filter(Boolean);
  }

  // Teacher-specific edit steps (themes management) in precise order and positions
  function getTeacherEditSteps() {
    var steps = [];
    // 1) Фото профілю
    steps.push(safeStep('.edit-profile-header .profile-image img, .edit-profile-header img#profile-preview', 'Фото профілю: За потреби оновіть аватар.'));
    // 2) Особиста інформація
    steps.push(safeStep('.edit-form .personal-info, .personal-info', 'Особиста інформація: Можливість редагувати чи додавати основні дані.'));
    // 3) Контакти
    steps.push(safeStep('.edit-form .contacts, .contacts', 'Контакти: Додайте робочі контакти для зв\'язку.'));
    // 4) Управління темами (зліва біля контейнера)
    steps.push(safeStepPos('.themes-section h3', 'Управління темами: Секція для управління Вашими темами.', 'bottom-left'));
    // 5) Додати нову тему
    steps.push(safeStep('.add-theme-btn, .add-theme', 'Додати нову тему: Створіть тему, вказавши назву, опис та відповідні потоки, для яких ця тема буде доступною.'));
    // 6) Редагування теми (праворуч від кнопки, але зверху на мобільних)
    steps.push(safeStepPos('.themes-grid .theme-card:first-child .edit-btn', 'Редагувати тему: Змініть назву, опис або потоки.', 'right', 0, 0, true));
    // 7) Активація та 8) Деактивація (праворуч, але зверху на мобільних)
    steps.push(safeStepPos('.themes-grid .theme-card:first-child .activate-btn', 'Активувати тему: Активація теми робить її доступною для нових запитів.', 'right', 0, 0, true));
    steps.push(safeStepPos('.themes-grid .theme-card:first-child .deactivate-btn', 'Деактивувати тему: Тимчасово приховує тему для нових запитів без видалення.', 'right', 0, 0, true));
    // 9) Видалення (праворуч, але зверху на мобільних)
    steps.push(safeStepPos('.themes-grid .theme-card:first-child .delete-btn', 'Видалити тему: Повне видалення теми.', 'right', 0, 0, true));
    // 10) Потоки
    steps.push(safeStep('.themes-grid .theme-card:first-child .streams-list, .themes-grid .theme-card:first-child .theme-streams-container', 'Потоки: Оберіть академічні потоки, для яких доступна тема.'));
    // 11) Активна/статус
    steps.push(safeStep('.themes-grid .theme-card:first-child .status-indicator', 'Активна/Неактивна: Поточний статус теми, що вказує на її видимість для студентів.'));
    // 12) Запити
    steps.push(safeStep('.themes-grid .theme-card:first-child .requests-count', 'Запити: Кількість поданих запитів студентів на цю тему.'));
    // 13) Зберегти (справа від кнопки, але зверху на мобільних)
    steps.push(safeStepPos('.save-button', 'Зберегти: Збережіть щойно внесені зміни профілю.', 'right', 0, 0, true));
    // 14) Завершити (справа від кнопки, але зверху на мобільних)
    steps.push(safeStepPos('.back-button', 'Завершити: Повернутися до сторінки профілю після збереження змін.', 'right', 0, 0, true));
    return steps.filter(Boolean);
  }

  function getStudentEditSteps() {
    return getEditProfileSteps();
  }

  function getTeacherRequestsSteps() {
    return [
      safeStep('.pending-section .request-button.accept', 'Прийняти запит студента: прийміть запит, попередньо обравши тему з Вашого переліку чи з запропонованих студентом.'),
      safeStep('.pending-section .request-button.reject', 'Відхилити запит: вкажіть причину відмови та відхиліть запит студента.'),
    ].filter(Boolean);
  }

  function getTeacherHomeSteps() {
    return [
      safeStep('#nav-home', 'Головна: останні оголошення, корисні матеріали, дедлайни та актуальна інформація.'),
    ].filter(Boolean);
  }

  function resolveSteps(role, context) {
    var steps = [];
    // Header tips: on PROFILE (as раніше), on HOME (student+teacher), on CATALOG (student only)
    if (isProfilePage()) {
    steps = steps.concat(getCommonHeaderSteps());
    }

    var isStudent = role && role.indexOf('Студент') !== -1;
    var isTeacher = role && (role.indexOf('Викладач') !== -1 || role.toLowerCase().indexOf('викл') !== -1);

    if (context === 'edit' || isEditProfilePage()) {
      if (isTeacher) {
        steps = steps.concat(getTeacherEditSteps());
      } else {
        steps = steps.concat(getStudentEditSteps());
      }
    } else if (context === 'catalog' || isCatalogPage()) {
    if (isStudent) {
        steps = steps.concat(getStudentCatalogSteps());
      } else {
        steps = steps.concat(getStudentCatalogSteps()); // Same steps for teachers
      }
    } else if (isStudent) {
      if (isCatalogPage()) steps = steps.concat(getStudentCatalogSteps());
      if (isProfilePage()) steps = steps.concat(getStudentProfileSteps());
      if (isHomePage()) steps = steps.concat(getStudentHomeSteps());
      if (isHomePage()) steps = steps.concat(getHeaderNavSteps(true));
      if (isCatalogPage()) steps = steps.concat(getHeaderNavSteps(true));
    } else if (isTeacher) {
      if (isHomePage()) steps = steps.concat(getTeacherHomeSteps());
      if (isProfilePage()) steps = steps.concat(getTeacherProfileSteps());
      if (isHomePage()) steps = steps.concat(getHeaderNavSteps(false));
    } else {
      // fallback minimal tour
      steps.push(safeStep('#nav-home', 'Вітаємо! Це головне меню навігації.'));
    }

    // remove nulls and ensure elements exist
    return steps.filter(Boolean);
  }

  function ensureTourCss() {
    try {
      if (!document.querySelector('link[href*="intro_tour.css"]')) {
        var custom = document.createElement('link');
        custom.rel = 'stylesheet';
        custom.href = '/static/css/intro_tour.css';
        document.head.appendChild(custom);
      }
    } catch (_) { /* noop */ }
  }

  function setFooterProgress(tour, stepCount) {
    try {
      var tooltip = document.querySelector('.introjs-tooltip.tour-card');
      if (!tooltip) return;
      var footer = tooltip.querySelector('.introjs-tooltipbuttons');
      if (!footer) return;
      var progress = footer.querySelector('.tour-progress');
      if (!progress) {
        progress = document.createElement('div');
        progress.className = 'tour-progress';
        footer.insertBefore(progress, footer.firstChild);
      }
      var currentIdx = (typeof tour.currentStep === 'function' ? tour.currentStep() : (tour._currentStep || 0)) + 1;
      progress.textContent = currentIdx + '/' + stepCount;
    } catch (_) { /* noop */ }
  }

  function bindTourLifecycle(tour, stepCount) {
    var cleanupFns = [];
    var originalOverlayStyle = null;
    var originalRefLayerStyle = null;

    function getBoundaryEl() {
      return document.querySelector('.profile-container') ||
             document.querySelector('.edit-profile-container') ||
             document.querySelector('.main-container-catalog') ||
             document.querySelector('.search-results') ||
             document.querySelector('main.profile-main') ||
             document.body;
    }

    function constrainToBoundary() {
      try {
        var boundary = getBoundaryEl();
        var overlay = document.querySelector('.introjs-overlay');
        var refLayer = document.querySelector('.introjs-tooltipReferenceLayer');
        if (!boundary || (!overlay && !refLayer)) return;
        var r = boundary.getBoundingClientRect();
        var top = Math.max(0, r.top + window.scrollY);
        var left = Math.max(0, r.left + window.scrollX);
        var width = Math.max(0, r.width);
        var height = Math.max(0, r.height);
        if (overlay) {
          if (originalOverlayStyle === null) originalOverlayStyle = overlay.getAttribute('style') || '';
          overlay.style.position = 'absolute';
          overlay.style.top = top + 'px';
          overlay.style.left = left + 'px';
          overlay.style.width = width + 'px';
          overlay.style.height = height + 'px';
          overlay.style.pointerEvents = 'auto';
          overlay.style.zIndex = '999999';
        }
        if (refLayer) {
          if (originalRefLayerStyle === null) originalRefLayerStyle = refLayer.getAttribute('style') || '';
          refLayer.style.position = 'absolute';
          refLayer.style.top = top + 'px';
          refLayer.style.left = left + 'px';
          refLayer.style.width = width + 'px';
          refLayer.style.height = height + 'px';
          refLayer.style.overflow = 'visible';
        }
      } catch (_) { /* noop */ }
    }

    function update() {
      try {
        setFooterProgress(tour, stepCount);
      } catch (_) {}
      try {
        tour.refresh();
      } catch (_) {}
      constrainToBoundary();
      // ensure helper has our classes every step
      try {
        var hl = document.querySelector('.introjs-helperLayer');
        if (hl && hl.className.indexOf('tour-pulse') === -1) hl.classList.add('tour-pulse');
      } catch (_) {}
    }

    function deferredUpdate() { setTimeout(update, 0); }

    try {
      tour.onbeforechange(deferredUpdate);
      tour.onafterchange(deferredUpdate);
      tour.onchange(deferredUpdate);
    } catch (_) {}

    var onResize = deferredUpdate;
    var onScroll = deferredUpdate;
    window.addEventListener('resize', onResize);
    window.addEventListener('scroll', onScroll, true);
    cleanupFns.push(function(){
      window.removeEventListener('resize', onResize);
      window.removeEventListener('scroll', onScroll, true);
    });

    // Observe tooltip re-renders so progress is re-injected reliably
    try {
      var observer = new MutationObserver(function () { deferredUpdate(); });
      observer.observe(document.body, { childList: true, subtree: true });
      cleanupFns.push(function(){ observer.disconnect(); });
    } catch (_) {}

    // Cleanup on exit
    try {
      function restoreLayers(){
        try {
          var overlay = document.querySelector('.introjs-overlay');
          var refLayer = document.querySelector('.introjs-tooltipReferenceLayer');
          if (overlay && originalOverlayStyle !== null) overlay.setAttribute('style', originalOverlayStyle);
          if (refLayer && originalRefLayerStyle !== null) refLayer.setAttribute('style', originalRefLayerStyle);
        } catch (_) {}
      }
      tour.onexit(function(){ restoreLayers(); cleanupFns.forEach(function(fn){ try{ fn(); } catch(_){} }); });
      tour.oncomplete(function(){ restoreLayers(); cleanupFns.forEach(function(fn){ try{ fn(); } catch(_){} }); });
    } catch (_) {}
  }

  function startTour(context) {
    ensureTourCss();
    var role = (window.APP_ROLE || '').toString();
    var steps = resolveSteps(role, context);
    if (!steps.length) return;
    // Transform plain text steps into richer HTML with icon, title, text
    var stepCount = steps.length;
    var htmlSteps = steps.map(function (s, idx) {
      if (!s || !s.element || !s.intro) return s;
      var text = s.intro;
      var parts = String(text).split(': ');
      var title = parts.length > 1 ? parts[0] : '';
      var body = parts.length > 1 ? parts.slice(1).join(': ') : text;
      s.intro = '<div class="tour-step">' +
                '  <div class="tour-content">' +
                (title ? ('<h3 class="tour-title">' + title + '</h3>') : '') +
                '    <p class="tour-text">' + body + '</p>' +
                '  </div>' +
                '</div>';
      return s;
    });

    var tour = introJs();
    tour.setOptions({
      steps: htmlSteps,
      nextLabel: 'Зрозуміло',
      prevLabel: 'Назад',
      skipLabel: '',
      doneLabel: 'Готово',
      showProgress: false,
      showBullets: false,
      disableInteraction: false,
      tooltipClass: 'tour-card',
      tooltipPosition: 'auto',
      positionPrecedence: ['bottom', 'top', 'right', 'left'],
      scrollTo: true,
      scrollToElement: true,
      scrollPadding: 100,
      exitOnOverlayClick: true,
      helperElementPadding: 12
    });

    bindTourLifecycle(tour, stepCount);
    // add pulsing class to helper layer on each step and auto-fix tooltip direction
    tour.onafterchange(function(){
      try {
        var hl = document.querySelector('.introjs-helperLayer');
        if (hl) {
          hl.classList.add('tour-pulse');
        }
        
        // Додаткове прокручування до елемента, якщо він не видно
        var stepIndex = typeof tour.currentStep === 'function' ? tour.currentStep() : tour._currentStep || 0;
        var item = (tour._introItems && tour._introItems[stepIndex]) || null;
        if (item && item.element) {
          var element = item.element;
          var rect = element.getBoundingClientRect();
          var isVisible = rect.top >= 0 && rect.bottom <= window.innerHeight;
          
          if (!isVisible) {
            // Прокручуємо до елемента з відступом
            var isMobile = window.innerWidth <= 640;
            
            // Перевіряємо чи елемент знаходиться в скролюваному контейнері
            var scrollableContainer = element.closest('.themes-grid, .themes-section, .form-content, .edit-profile-container');
            if (scrollableContainer && scrollableContainer.scrollHeight > scrollableContainer.clientHeight) {
              // Прокручуємо всередині контейнера
              var containerRect = scrollableContainer.getBoundingClientRect();
              var elementRect = element.getBoundingClientRect();
              var scrollTop = scrollableContainer.scrollTop + (elementRect.top - containerRect.top) - (isMobile ? 50 : 100);
              
              // Переконуємося, що scrollTop не негативний
              scrollTop = Math.max(0, scrollTop);
              
              scrollableContainer.scrollTo({
                top: scrollTop,
                behavior: 'smooth'
              });
              
              // Додаткове прокручування сторінки, якщо контейнер не видимий
              if (containerRect.top < 0 || containerRect.bottom > window.innerHeight) {
                setTimeout(function() {
                  scrollableContainer.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start',
                    inline: 'nearest'
                  });
                }, 300);
              }
            } else {
              // Звичайне прокручування сторінки
              element.scrollIntoView({
                behavior: 'smooth',
                block: isMobile ? 'start' : 'center',
                inline: 'nearest'
              });
            }
          }
        }
        // choose the best direction within boundary to avoid overlap
        if (item && item._strict) {
          // Check if mobile and should use top position
          var isMobile = window.innerWidth <= 640;
          if (isMobile && item.mobileTop && (item.position === 'right' || item.position === 'left')) {
            item.position = 'top';
            tour.refresh();
          }
          
          // Додаткова логіка для кнопок збереження на мобільних
          if (isMobile && item.element) {
            var element = item.element;
            var isSaveButton = element.classList.contains('save-button') || element.classList.contains('back-button');
            if (isSaveButton) {
              item.position = 'top';
              tour.refresh();
            }
          }
          
          // Спеціальна логіка для кнопок "Надіслати запит"
          if (item.element) {
            var element = item.element;
            var isModalButton = element.classList.contains('modal-button') || element.classList.contains('theme-select-btn') || element.classList.contains('topic-select-btn');
            if (isModalButton) {
              item.position = 'left';
              tour.refresh();
            }
          }
          
          // Спеціальна логіка для фільтрів на мобільних
          if (item.element) {
            var element = item.element;
            var isMobileFilter = element.classList.contains('mobile-filter-bar');
            if (isMobileFilter) {
              item.position = 'bottom';
              tour.refresh();
            }
          }
          
          // Спеціальна логіка для сповіщень - максимально ліворуч
          if (item.element) {
            var element = item.element;
            var isNotificationButton = element.id === 'dropdownMenuButton' || element.id === 'messageDropdownButton';
            if (isNotificationButton) {
              item.position = 'left';
              tour.refresh();
            }
          }
          
          // Спеціальна логіка для результатів - завжди знизу
          if (item.element) {
            var element = item.element;
            var isResultsContainer = element.classList.contains('teachers-list') || 
                                   element.classList.contains('unified-results') || 
                                   element.classList.contains('catalog-container') || 
                                   element.classList.contains('themes-list') || 
                                   element.classList.contains('all-content') || 
                                   element.classList.contains('search-results') ||
                                   element.classList.contains('results-section');
            if (isResultsContainer) {
              item.position = 'bottom';
              tour.refresh();
            }
          }
          
          // Apply offsets for strict positioned steps if they exist
          if (item.offsetY !== undefined || item.offsetX !== undefined) {
            var tooltip = document.querySelector('.introjs-tooltip');
            if (tooltip) {
              if (item.offsetY !== undefined) {
                var currentTop = parseInt(tooltip.style.top) || 0;
                tooltip.style.setProperty('top', (currentTop + item.offsetY) + 'px', 'important');
              }
              if (item.offsetX !== undefined) {
                var currentLeft = parseInt(tooltip.style.left) || 0;
                tooltip.style.setProperty('left', (currentLeft + item.offsetX) + 'px', 'important');
              }
            }
            // Apply offsets again after a short delay to override any Intro.js repositioning
            setTimeout(function() {
              var tooltip = document.querySelector('.introjs-tooltip');
              if (tooltip && item) {
                var isMobile = window.innerWidth <= 640;
                var isSaveButton = item.element && (item.element.classList.contains('save-button') || item.element.classList.contains('back-button'));
                
                // Примусове позиціонування для кнопок збереження на мобільних
                if (isMobile && isSaveButton) {
                  var elementRect = item.element.getBoundingClientRect();
                  var tooltipHeight = tooltip.offsetHeight || 100;
                  var newTop = elementRect.top - tooltipHeight - 20; // 20px відступ вгору
                  
                  tooltip.style.setProperty('top', newTop + 'px', 'important');
                  tooltip.style.setProperty('left', '50%', 'important');
                  tooltip.style.setProperty('transform', 'translateX(-50%)', 'important');
                } else {
                  if (item.offsetY !== undefined) {
                    var currentTop = parseInt(tooltip.style.top) || 0;
                    var offsetY = item.offsetY;
                    
                    // Додатковий відступ для кнопок збереження на мобільних
                    if (isMobile && isSaveButton && item.position === 'top') {
                      offsetY = offsetY - 20; // Додатковий відступ вгору
                    }
                    
                    tooltip.style.setProperty('top', (currentTop + offsetY) + 'px', 'important');
                  }
                  if (item.offsetX !== undefined) {
                    var currentLeft = parseInt(tooltip.style.left) || 0;
                    tooltip.style.setProperty('left', (currentLeft + item.offsetX) + 'px', 'important');
                  }
                }
              }
            }, 50);
            
            // Додатковий setTimeout для кнопок збереження
            if (isMobile && item.element && (item.element.classList.contains('save-button') || item.element.classList.contains('back-button'))) {
              setTimeout(function() {
                var tooltip = document.querySelector('.introjs-tooltip');
                if (tooltip && item.element) {
                  var elementRect = item.element.getBoundingClientRect();
                  var tooltipHeight = tooltip.offsetHeight || 100;
                  var newTop = elementRect.top - tooltipHeight - 20;
                  
                  tooltip.style.setProperty('top', newTop + 'px', 'important');
                  tooltip.style.setProperty('left', '50%', 'important');
                  tooltip.style.setProperty('transform', 'translateX(-50%)', 'important');
                }
              }, 100);
            }
            
            // Додатковий setTimeout для кнопок "Надіслати запит"
            if (item.element && (item.element.classList.contains('modal-button') || item.element.classList.contains('theme-select-btn') || item.element.classList.contains('topic-select-btn'))) {
              setTimeout(function() {
                var tooltip = document.querySelector('.introjs-tooltip');
                if (tooltip && item.element) {
                  var elementRect = item.element.getBoundingClientRect();
                  var tooltipWidth = tooltip.offsetWidth || 260;
                  var newLeft = elementRect.left - tooltipWidth - 80; // 80px відступ ліворуч
                  
                  tooltip.style.setProperty('left', newLeft + 'px', 'important');
                  tooltip.style.setProperty('top', elementRect.top + 'px', 'important');
                  tooltip.style.setProperty('transform', 'none', 'important');
                }
              }, 100);
            }
            
            // Додатковий setTimeout для мобільних фільтрів
            if (item.element && item.element.classList.contains('mobile-filter-bar')) {
              setTimeout(function() {
                var tooltip = document.querySelector('.introjs-tooltip');
                if (tooltip && item.element) {
                  var elementRect = item.element.getBoundingClientRect();
                  var tooltipHeight = tooltip.offsetHeight || 100;
                  var newTop = elementRect.bottom + 20; // 20px відступ вниз
                  
                  tooltip.style.setProperty('top', newTop + 'px', 'important');
                  tooltip.style.setProperty('left', '50%', 'important');
                  tooltip.style.setProperty('transform', 'translateX(-50%)', 'important');
                }
              }, 100);
            }
            
            // Додатковий setTimeout для результатів
            if (item.element && (item.element.classList.contains('teachers-list') || 
                               item.element.classList.contains('unified-results') || 
                               item.element.classList.contains('catalog-container') || 
                               item.element.classList.contains('themes-list') || 
                               item.element.classList.contains('all-content') || 
                               item.element.classList.contains('search-results') ||
                               item.element.classList.contains('results-section'))) {
              setTimeout(function() {
                var tooltip = document.querySelector('.introjs-tooltip');
                if (tooltip && item.element) {
                  var elementRect = item.element.getBoundingClientRect();
                  var tooltipHeight = tooltip.offsetHeight || 100;
                  var newTop = elementRect.bottom + 30; // 30px відступ вниз
                  
                  tooltip.style.setProperty('top', newTop + 'px', 'important');
                  tooltip.style.setProperty('left', '50%', 'important');
                  tooltip.style.setProperty('transform', 'translateX(-50%)', 'important');
                }
              }, 100);
              
              // Спеціальна логіка для results-section (комбінований режим) - як у режимі викладачів
              if (item.element.classList.contains('results-section')) {
                setTimeout(function() {
                  var tooltip = document.querySelector('.introjs-tooltip');
                  if (tooltip && item.element) {
                    // Знаходимо перший .catalog-container всередині results-section
                    var catalogContainer = item.element.querySelector('.catalog-container');
                    if (catalogContainer) {
                      var elementRect = catalogContainer.getBoundingClientRect();
                      var tooltipHeight = tooltip.offsetHeight || 100;
                      var newTop = elementRect.bottom + 30; // 30px відступ вниз як у викладачів
                      
                      tooltip.style.setProperty('top', newTop + 'px', 'important');
                      tooltip.style.setProperty('left', '50%', 'important');
                      tooltip.style.setProperty('transform', 'translateX(-50%)', 'important');
                      tooltip.style.setProperty('z-index', '999999', 'important');
                    } else {
                      // Fallback до results-section
                      var elementRect = item.element.getBoundingClientRect();
                      var tooltipHeight = tooltip.offsetHeight || 100;
                      var newTop = elementRect.bottom + 30;
                      
                      tooltip.style.setProperty('top', newTop + 'px', 'important');
                      tooltip.style.setProperty('left', '50%', 'important');
                      tooltip.style.setProperty('transform', 'translateX(-50%)', 'important');
                      tooltip.style.setProperty('z-index', '999999', 'important');
                    }
                  }
                }, 150);
              }
            }
            
            // Додатковий setTimeout для сповіщень - максимально ліворуч
            if (item.element && (item.element.id === 'dropdownMenuButton' || item.element.id === 'messageDropdownButton')) {
              setTimeout(function() {
                var tooltip = document.querySelector('.introjs-tooltip');
                if (tooltip && item.element) {
                  var elementRect = item.element.getBoundingClientRect();
                  var tooltipWidth = tooltip.offsetWidth || 260;
                  var newLeft = elementRect.left - tooltipWidth - 120; // 120px відступ ліворуч
                  
                  tooltip.style.setProperty('left', newLeft + 'px', 'important');
                  tooltip.style.setProperty('top', elementRect.top + 'px', 'important');
                  tooltip.style.setProperty('transform', 'none', 'important');
                  tooltip.style.setProperty('z-index', '999999', 'important');
                }
              }, 100);
            }
            
            // Додатковий setTimeout для кнопок модалки з більшою затримкою
            if (item.element && (item.element.classList.contains('modal-button') || item.element.classList.contains('theme-select-btn') || item.element.classList.contains('topic-select-btn'))) {
              setTimeout(function() {
                var tooltip = document.querySelector('.introjs-tooltip');
                if (tooltip && item.element) {
                  var elementRect = item.element.getBoundingClientRect();
                  var tooltipWidth = tooltip.offsetWidth || 260;
                  var newLeft = elementRect.left - tooltipWidth - 100; // 100px відступ ліворуч
                  
                  tooltip.style.setProperty('left', newLeft + 'px', 'important');
                  tooltip.style.setProperty('top', elementRect.top + 'px', 'important');
                  tooltip.style.setProperty('transform', 'none', 'important');
                  tooltip.style.setProperty('z-index', '999999', 'important');
                }
              }, 200);
              
              // Ще один setTimeout для повної гарантії
              setTimeout(function() {
                var tooltip = document.querySelector('.introjs-tooltip');
                if (tooltip && item.element) {
                  var elementRect = item.element.getBoundingClientRect();
                  var tooltipWidth = tooltip.offsetWidth || 260;
                  var newLeft = elementRect.left - tooltipWidth - 120; // 120px відступ ліворуч
                  
                  tooltip.style.setProperty('left', newLeft + 'px', 'important');
                  tooltip.style.setProperty('top', elementRect.top + 'px', 'important');
                  tooltip.style.setProperty('transform', 'none', 'important');
                  tooltip.style.setProperty('z-index', '999999', 'important');
                }
              }, 300);
            }
          }
          return; // honor strict positioning
        }
        var el = item && item.element ? item.element : null;
        var tooltip = document.querySelector('.introjs-tooltip');
        if (el && tooltip) {
          var boundary = document.querySelector('.profile-container') || document.querySelector('.edit-profile-container') || document.querySelector('.main-container-catalog') || document.querySelector('.search-results') || document.body;
          var b = boundary.getBoundingClientRect();
          var r = el.getBoundingClientRect();
          var tw = tooltip.offsetWidth || 260;
          var th = tooltip.offsetHeight || 160;
          var m = 16;
          var fitsBottom = (r.bottom + m + th) <= b.bottom;
          var fitsTop = (r.top - m - th) >= b.top;
          var fitsRight = (r.right + m + tw) <= b.right;
          var fitsLeft = (r.left - m - tw) >= b.left;
          var chosen = 'bottom';
          if (fitsBottom) chosen = 'bottom';
          else if (fitsTop) chosen = 'top';
          else if (fitsRight) chosen = 'right';
          else if (fitsLeft) chosen = 'left';
          else {
            // fallback to the side with most space
            var space = {
              bottom: b.bottom - r.bottom,
              top: r.top - b.top,
              right: b.right - r.right,
              left: r.left - b.left
            };
            chosen = Object.keys(space).sort(function(a,bk){ return space[bk]-space[a]; })[0] || 'bottom';
          }
          if (item.position !== chosen) {
            item.position = chosen;
            tour.refresh();
          }
        }
      } catch (_) { /* noop */ }
    });
    tour.start();
    setTimeout(function(){ setFooterProgress(tour, stepCount); tour.refresh(); }, 0);
  }

  document.addEventListener('DOMContentLoaded', function () {
    var triggers = Array.prototype.slice.call(document.querySelectorAll('#start-tour, #start-tour-profile, #start-tour-edit, #start-tour-catalog, #start-tour-catalog-mobile, .start-tour'));
    triggers.forEach(function(btn){
      btn.addEventListener('click', function (e) {
      e.preventDefault();
        var ctx = btn.getAttribute('data-tour') || 
                  (btn.id && btn.id.indexOf('edit') !== -1 ? 'edit' : undefined) ||
                  (btn.id && btn.id.indexOf('catalog') !== -1 ? 'catalog' : undefined);
        ensureIntroLoaded().then(function(){ startTour(ctx); }).catch(function(){ /* noop */ });
      });
    });
  });

  window.startTour = startTour;
})();

// Lazy loader for Intro.js in case CDN hasn't loaded yet
function ensureIntroLoaded() {
  return new Promise(function (resolve, reject) {
    if (window.introJs) {
      // Intro is already on the page (e.g., loaded from template). Make sure our CSS is present too.
      try { ensureTourCss(); } catch (_) {}
      return resolve();
    }
    try {
      // Inject CSS if missing
      if (!document.querySelector('link[href*="introjs"]')) {
        var link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = 'https://unpkg.com/intro.js/minified/introjs.min.css';
        document.head.appendChild(link);
      }
      // Inject our custom tour CSS once
      ensureTourCss();
      // Inject JS
      var script = document.createElement('script');
      script.src = 'https://unpkg.com/intro.js/minified/intro.min.js';
      script.onload = function () { resolve(); };
      script.onerror = function () { reject(new Error('Intro.js failed to load')); };
      document.body.appendChild(script);
    } catch (e) {
      reject(e);
    }
  });
}


