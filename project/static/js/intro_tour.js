/* Role- and page-aware Intro.js tour */
(function () {
  function isCatalogPage() {
    return !!document.querySelector(".main-container-catalog");
  }

  function isProfilePage() {
    return !!document.querySelector(".profile-container");
  }

  function isEditProfilePage() {
    return !!document.querySelector(".edit-profile-container");
  }

  function isCatalogPage() {
    return !!document.querySelector(".main-container-catalog");
  }

  function isHomePage() {
    return !!document.querySelector(
      ".main-content .section-header .section-title"
    );
  }

  function defined(element) {
    return !!element;
  }

  function safeStep(selector, intro) {
    var el =
      typeof selector === "string" ? pickBestElement(selector) : selector;
    return el ? { element: el, intro: intro } : null;
  }

  function safeStepPos(
    selector,
    intro,
    position,
    offsetY,
    offsetX,
    mobileTop = false
  ) {
    var el =
      typeof selector === "string" ? pickBestElement(selector) : selector;
    if (!el) return null;
    var step = { element: el, intro: intro, position: position };
    if (offsetY !== undefined) step.offsetY = offsetY;
    if (offsetX !== undefined) step.offsetX = offsetX;
    if (mobileTop) step.mobileTop = mobileTop;
    return step;
  }

  function getBoundaryRect() {
    var boundary =
      document.querySelector(".profile-container") ||
      document.querySelector(".edit-profile-container") ||
      document.querySelector(".main-container-catalog") ||
      document.querySelector(".search-results") ||
      document.querySelector("main.profile-main") ||
      document.body;
    return boundary.getBoundingClientRect();
  }

  // Choose the most relevant element for a selector: visible and closest to container center
  function pickBestElement(selector) {
    try {
      var list = Array.prototype.slice.call(
        document.querySelectorAll(selector)
      );

      if (!list.length) {
        return null;
      }

      var b = getBoundaryRect();
      var cx = (b.left + b.right) / 2;
      var cy = (b.top + b.bottom) / 2;
      var best = null;
      var bestScore = Infinity;

      list.forEach(function (el, index) {
        var r = el.getBoundingClientRect();
        // Більш м'яка перевірка видимості - елемент має бути в DOM і мати розміри
        var visible = r.width > 0 && r.height > 0;
        if (!visible) return;
        var dx = (r.left + r.right) / 2 - cx;
        var dy = (r.top + r.bottom) / 2 - cy;
        var score = dx * dx + dy * dy; // distance squared to center
        if (score < bestScore) {
          bestScore = score;
          best = el;
        }
      });

      return best || list[0];
    } catch (e) {
      return document.querySelector(selector);
    }
  }

  function getCommonHeaderSteps() {
    const burgerStep = getBurgerStep();
    if (burgerStep) return [burgerStep];

    return [
      safeStep(
        "#nav-home",
        "Головна: тут зібрана вся важлива інформація, включно з дедлайнами, оголошеннями та структурою курсових робіт."
      ),
      safeStep(
        "#nav-search",
        "Список викладачів: знайдіть викладача або тему для своєї роботи."
      ),
      safeStepPos(
        "#dropdownMenuButton, #messageDropdownButton",
        "Сповіщення та повідомлення: слідкуйте за повідомленнями та статусом роботи чи запиту.",
        "left",
        0,
        -100
      ),
    ].filter(Boolean);
  }

  // Header steps for Home and Catalog pages
  function getHeaderNavSteps(isStudent) {
    const burgerStep = getBurgerStep();
    if (burgerStep) return [burgerStep];
    return [
      getBurgerStep(),
      safeStep(
        "#nav-home",
        "Головна: тут зібрана вся важлива інформація, включно з дедлайнами, оголошеннями та структурою курсових робіт.",
        "bottom"
      ),
      isStudent
        ? safeStep(
            "#nav-search",
            "Список викладачів: знайдіть викладача або тему для своєї роботи.",
            "bottom"
          )
        : null,
      safeStepPos(
        "#dropdownMenuButton, #messageDropdownButton",
        "Сповіщення та повідомлення: слідкуйте за повідомленнями та статусом роботи чи запиту.",
        "left",
        0,
        -120
      ),
    ].filter(Boolean);
  }

  // STUDENT page-specific steps
  function getStudentCatalogSteps() {
    return [
      safeStepPos(
        ".search-section .form-searching",
        "Пошук викладача або теми: введіть запит та натисніть Enter.",
        "bottom"
      ),
      safeStepPos(
        ".segment-switcher",
        "Режими пошуку: перемикайтеся між викладачами, темами або обома одразу.",
        "bottom"
      ),
      safeStepPos(
        ".filter-section, .mobile-filter-bar",
        "Фільтри: оберіть кафедру або к-сть місць, щоб швидше знайти потрібне.",
        "right"
      ),
      safeStepPos(
        ".teachers-list, .unified-results, .catalog-container, .themes-list, .all-content, .search-results, .results-section",
        "Результати: клікніть на викладача, щоб переглянути його профіль, або натисніть на стрілочку на картці, щоб надіслати запит.",
        "bottom"
      ),
    ].filter(Boolean);
  }

  function getStudentProfileSteps() {
    var steps = [];
    // 1. Запити
    steps.push(
      safeStep(
        '.tabs .tab[data-tab="requests"]',
        "Вкладка «Запити»: стежте за статусом надісланих запитів до викладачів."
      )
    );
    // 2. Активні
    steps.push(
      safeStep(
        '.tabs .tab[data-tab="active"]',
        "Вкладка «Активні»: вся інформація про поточну роботу."
      )
    );
    steps.push(
      safeStep(
        "#active-section .files-scroll-container",
        "Файли поточної роботи: переглядайте, завантажуйте матеріали та тримайте зв'язок із викладачем."
      )
    );
    steps.push(
      safeStep(
        "#active-section .file-upload-form .file-input-label, #active-section .file-upload-btn",
        "Додайте файл до активної роботи."
      )
    );
    // 3. Архів
    steps.push(
      safeStep(
        '.tabs .tab[data-tab="archive"]',
        "Вкладка «Архів»: переглядайте завершені роботи та бали, виставлені викладачем."
      )
    );
    // 4. Редагування
    steps.push(
      safeStep(
        '.profile-buttons a[href*="edit"], .profile-buttons i.fa-edit',
        "Редагування профілю: змініть контактні дані або фото профілю за потреби."
      )
    );
    return steps.filter(Boolean);
  }

  function getStudentHomeSteps() {
    return [
      safeStep(
        "#nav-home",
        "Головна: тут зібрані важливі оголошення та матеріали."
      ),
      safeStep(
        ".section-title",
        "Актуальна інформація: слідкуйте за дедлайнами та оновленнями."
      ),
    ].filter(Boolean);
  }

  // TEACHER page-specific steps
  function getTeacherProfileSteps() {
    var steps = [];
    // 0. Редагування профілю — одразу після підказок хедера
    steps.push(
      safeStep(
        '.profile-buttons a[href*="edit"], .profile-buttons i.fa-edit',
        "Редагування профілю: змініть контактні дані, фото та іншу інформацію."
      )
    );
    // 1. Інформація
    steps.push(
      safeStep(
        '.tabs .tab[data-tab="info"]',
        "Вкладка «Інформація»: переглядайте перелік своїх тем та доступні місця для потоків."
      )
    );
    steps.push(
      safeStep(".add-theme, .add-theme-btn", "Додайте нову тему для студентів.")
    );
    // 2. Запити
    steps.push(
      safeStep(
        '.tabs .tab[data-tab="requests"]',
        "Вкладка «Запити»: керуйте запитами студентів."
      )
    );
    steps.push(
      safeStep(
        ".pending-section .request-button.accept",
        "Прийняти запит: оберіть тему та підтвердіть запит студента."
      )
    );
    steps.push(
      safeStep(
        ".pending-section .request-button.reject",
        "Відхилити запит: вкажіть причину та відхиліть запит студента."
      )
    );
    // 3. Активні
    steps.push(
      safeStep(
        '.tabs .tab[data-tab="active"]',
        "Вкладка «Активні»: перегляньте актуальні роботи зі студентами."
      )
    );
    steps.push(
      safeStep(
        "#active-section .edit-theme-btn",
        "Редагуйте тему активної роботи за потреби."
      )
    );
    steps.push(
      safeStep(
        "#active-section .file-upload-form .file-input-label, #active-section .file-upload-btn",
        "Надішліть файл стосовно активної роботи."
      )
    );
    steps.push(
      safeStep(
        "#active-section .comment-textarea, #active-section .add-comment-btn",
        "Лишайте коментарі та фідбек для студента."
      )
    );
    steps.push(
      safeStepPos(
        "#active-section .complete-button",
        "Завершити роботу: виставіть оцінку та перемістіть роботу в архів.",
        "top"
      )
    );
    steps.push(
      safeStepPos(
        "#active-section .cancel-button",
        "Скасувати роботу, якщо запит прийнято помилково.",
        "top"
      )
    );
    // 4. Архів
    steps.push(
      safeStep(
        '.tabs .tab[data-tab="archive"]',
        "Вкладка «Архів»: переглядайте завершені роботи та надіслані файли."
      )
    );
    return steps.filter(Boolean);
  }

  // EDIT PROFILE page core steps (common)
  function getEditProfileSteps() {
    var steps = [];
    steps.push(
      safeStep(
        ".edit-profile-header .profile-image img, .edit-profile-header img#profile-preview",
        "Фото профілю: оновіть аватар за потреби."
      )
    );
    steps.push(
      safeStep(
        ".edit-form .personal-info, .personal-info",
        "Особиста інформація: редагуйте або додавайте основні дані."
      )
    );
    steps.push(
      safeStep(
        ".edit-form .contacts, .contacts",
        "Контакти: додайте робочі способи зв'язку."
      )
    );
    steps.push(
      safeStepPos(
        ".save-button",
        "Зберегти зміни профілю.",
        "right",
        0,
        0,
        true
      )
    );
    steps.push(
      safeStepPos(
        ".back-button",
        "Завершити редагування та повернутися до профілю.",
        "right",
        0,
        0,
        true
      )
    );
    return steps.filter(Boolean);
  }

  // Teacher-specific edit steps (themes management) in precise order and positions
  function getTeacherEditSteps() {
    var steps = [];
    // 1) Фото профілю
    steps.push(
      safeStep(
        ".edit-profile-header .profile-image img, .edit-profile-header img#profile-preview",
        "Фото профілю: оновіть аватар при потребі."
      )
    );
    // 2) Особиста інформація
    steps.push(
      safeStep(
        ".edit-form .personal-info, .personal-info",
        "Особиста інформація: редагуйте або додавайте основні дані."
      )
    );
    // 3) Контакти
    steps.push(
      safeStep(
        ".edit-form .contacts, .contacts",
        "Контакти: додайте робочі способи зв'язку."
      )
    );
    // 4) Управління темами (зліва біля контейнера)
    steps.push(
      safeStep(
        ".themes-section h3",
        "Управління темами: керуйте своїми темами."
      )
    );
    // 5) Додати нову тему
    steps.push(
      safeStep(
        ".add-theme-btn, .add-theme",
        "Додати нову тему: вкажіть назву, опис та потоки, де тема доступна."
      )
    );
    // 6) Дії з темою (об'єднані)
    steps.push(
      safeStep(
        ".themes-grid .theme-card:first-child .theme-actions",
        "Дії з темою: Редагувати (змінити назву, опис, потоки), Активувати/Деактивувати (зробити доступною/недоступною для запитів), Видалити (повне видалення теми)."
      )
    );
    // 7) Зберегти
    steps.push(safeStep(".save-button", "Зберегти зміни профілю."));
    // 8) Завершити
    steps.push(
      safeStep(
        ".back-button",
        "Завершити редагування та повернутися до профілю."
      )
    );
    return steps.filter(Boolean);
  }

  function getStudentEditSteps() {
    return getEditProfileSteps();
  }

  function getTeacherRequestsSteps() {
    return [
      safeStep(
        ".pending-section .request-button.accept",
        "Прийняти запит студента: прийміть запит, попередньо обравши тему з Вашого переліку чи з запропонованих студентом."
      ),
      safeStep(
        ".pending-section .request-button.reject",
        "Відхилити запит: вкажіть причину відмови та відхиліть запит студента."
      ),
    ].filter(Boolean);
  }

  function getTeacherHomeSteps() {
    return [
      safeStep(
        "#nav-home",
        "Головна: останні оголошення, корисні матеріали, дедлайни та актуальна інформація."
      ),
    ].filter(Boolean);
  }

  function resolveSteps(role, context) {
    var steps = [];
    // Header tips: on PROFILE (as раніше), on HOME (student+teacher), on CATALOG (student only)
    if (isProfilePage()) {
      steps = steps.concat(getCommonHeaderSteps());
    }

    var isStudent = role && role.indexOf("Студент") !== -1;
    var isTeacher =
      role &&
      (role.indexOf("Викладач") !== -1 ||
        role.toLowerCase().indexOf("викл") !== -1);

    if (context === "edit" || isEditProfilePage()) {
      if (isTeacher) {
        steps = steps.concat(getTeacherEditSteps());
      } else {
        steps = steps.concat(getStudentEditSteps());
      }
    } else if (context === "catalog" || isCatalogPage()) {
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
      steps.push(safeStep("#nav-home", "Вітаємо! Це головне меню навігації."));
    }

    // remove nulls and ensure elements exist
    return steps.filter(Boolean);
  }

  function startTour(context) {
    // Приховуємо сповіщення під час туру
    var notificationDropdown = document.querySelector(".notification-dropdown");
    var messagePopup = document.querySelector(".message-popup");
    if (
      notificationDropdown &&
      notificationDropdown.classList.contains("show")
    ) {
      notificationDropdown.classList.remove("show");
    }
    if (messagePopup && messagePopup.classList.contains("show")) {
      messagePopup.classList.remove("show");
    }

    var role = (window.APP_ROLE || "").toString();
    var steps = resolveSteps(role, context);
    if (!steps.length) return;

    // Перетворюємо кроки для нашої власної системи
    var customSteps = steps
      .map(function (step) {
        if (!step || !step.element || !step.intro) return null;

        var text = step.intro;
        var parts = String(text).split(": ");
        var title = parts.length > 1 ? parts[0] : "";
        var body = parts.length > 1 ? parts.slice(1).join(": ") : text;

        return {
          element: step.element,
          title: title,
          text: body,
        };
      })
      .filter(Boolean);

    // Використовуємо нашу власну систему підказок
    if (window.startCustomTour) {
      window.startCustomTour(customSteps);
    } else {
      console.error("Custom tour system not loaded");
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    // Завантажуємо нашу власну систему підказок
    if (!document.querySelector('script[src*="custom_tour.js"]')) {
      var script = document.createElement("script");
      script.src = "/static/js/custom_tour.js";
      script.onload = function () {};
      document.head.appendChild(script);
    }

    var triggers = Array.prototype.slice.call(
      document.querySelectorAll(
        "#start-tour, #start-tour-profile, #start-tour-edit, #start-tour-catalog, #start-tour-catalog-mobile, .start-tour"
      )
    );
    triggers.forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.preventDefault();
        var ctx =
          btn.getAttribute("data-tour") ||
          (btn.id && btn.id.indexOf("edit") !== -1 ? "edit" : undefined) ||
          (btn.id && btn.id.indexOf("catalog") !== -1 ? "catalog" : undefined);

        // Використовуємо нашу власну систему
        startTour(ctx);
      });
    });
  });

  window.startTour = startTour;
})();

function getBurgerStep() {
  const el = document.querySelector("#burger-menu");
  if (!el) return null; // return null if burger doesn't exist

  // Check computed style for visibility
  const style = window.getComputedStyle(el);
  if (style.display === "none") return null;

  return {
    element: el,
    intro: "Меню навігації: натисніть, щоб відкрити навігацію по сайту.",
  };
}
