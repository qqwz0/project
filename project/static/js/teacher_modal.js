/**
 * Event listener triggered after the HTMX swap finishes inserting new content.
 * Shows a modal dialog when content is swapped into the inner_modal element.
 */
document.addEventListener("htmx:afterSwap", function (event) {
  if (event.detail.target.id === "inner_modal") {
    document.getElementById("details_request_modal").showModal();
  }

  // реініціалізація тултіпів після будь-якого swap
  initTooltips();
});
/**
 * Before swapping in new content with HTMX, if there's no response, reload the page.
 * This prevents issues when the HTMX request fails to return content.
 */
document.addEventListener("DOMContentLoaded", function () {
  initTooltips();
});

// Функція для ініціалізації тултіпів
function initTooltips() {
  if (typeof bootstrap !== "undefined") {
    let tooltipTriggerList = [].slice.call(
      document.querySelectorAll('[data-bs-toggle="tooltip"]')
    );
    tooltipTriggerList.map(function (tooltipTriggerEl) {
      return new bootstrap.Tooltip(tooltipTriggerEl);
    });
  } else if (typeof $ !== "undefined") {
    $('[data-bs-toggle="tooltip"]').tooltip();
  }
}

/**
 * Closes the popup message box when the 'Close' icon is clicked.
 * This is used for Django message framework popups.
 */
function closePopup() {
  const popup = document.querySelector(".success-popup");
  if (popup) {
    popup.style.display = "none";
  }
}

/**
 * Reprocesses HTMX bindings for all modal buttons after filtering.
 * Should be called after Alpine.js updates the filtered data.
 */
window.refreshHtmxBindings = function () {
  // Slight timeout to ensure Alpine.js has finished rendering
  setTimeout(() => {
    document.querySelectorAll(".modal-button").forEach((button) => {
      htmx.process(button);
    });
  }, 50);
};

document
  .getElementById("submit-btn")
  .addEventListener("click", function (event) {
    event.preventDefault();
    var form = document.getElementById("request-form");
    var actionUrl = form.dataset.actionUrl;

    var inputField = document.querySelector(
      'input[name="student_themes"]:not([type="hidden"])'
    );
    var pendingTheme = "";

    if (inputField && inputField.value.trim()) {
      pendingTheme = inputField.value.trim();
      inputField.value = "";
    }

    var formData = new FormData(form);
    var errorContainer = form.querySelector("#form-errors");
    errorContainer.textContent = "";

    fetch(actionUrl, {
      method: "POST",
      body: formData,
      headers: {
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": document.getElementById("csrf_token").value,
      },
    })
      .then((response) => {
        return response.json();
      })
      .then((data) => {
        if (!data.success && pendingTheme) {
          inputField.value = pendingTheme;
        }

        if (data.success) {
          document.getElementById("details_request_modal").close();
          location.reload();
        } else {
          const errorElements = [];
          for (var field in data.errors) {
            var fieldElement = document.querySelector(
              `[name="${field}"]:not([type="hidden"])`
            );
            var errorDiv = document.createElement("div");
            errorDiv.className = "error-message";
            errorDiv.textContent = data.errors[field].join(" | ");

            if (fieldElement) {
              var existingError =
                fieldElement.parentNode.querySelector(".error-message");
              if (existingError) {
                existingError.textContent = errorDiv.textContent;
                errorElements.push(existingError);
              } else {
                fieldElement.insertAdjacentElement("afterend", errorDiv);
                errorElements.push(errorDiv);
              }
            } else {
              errorContainer.appendChild(errorDiv);
              errorElements.push(errorDiv);
            }
          }

          setTimeout(() => {
            errorElements.forEach((element) => {
              element.remove();
            });
          }, 5000);
        }
      })
      .catch((error) => {
        console.error("Error:", error);
        if (pendingTheme) {
          inputField.value = pendingTheme;
        }
      });
  });

document
  .getElementById("dropdown-toggle")
  .addEventListener("click", function () {
    var dropdownMenu = document.getElementById("dropdown-menu");
    var isOpen = dropdownMenu.style.display === "block";

    dropdownMenu.style.display = isOpen ? "none" : "block";
    this.classList.toggle("active", !isOpen);
  });

// Handle dropdown item selection
document.querySelectorAll(".dropdown-item").forEach(function (item) {
  item.addEventListener("click", function () {
    document.querySelector('input[name="teacher_themes"]').value =
      this.getAttribute("data-value");
    document.getElementById("dropdown-menu").style.display = "none";
    document.getElementById("dropdown-toggle").classList.remove("active");
  });
});

// Close dropdown menu when clicking outside
document.addEventListener("click", function (event) {
  if (!event.target.closest(".dropdown")) {
    document.getElementById("dropdown-menu").style.display = "none";
    document.getElementById("dropdown-toggle").classList.remove("active");
  }
});

var themeInput = document.querySelector('input[name="student_themes"]');
var addButton = document.getElementById("add-theme");

addButton.addEventListener("click", function () {
  addTheme();
});

themeInput.addEventListener("keypress", function (e) {
  if (e.key === "Enter") {
    e.preventDefault();
    addTheme();
  }
});

themeInput.addEventListener("input", function () {
  checkButtonReadiness();
});

function checkButtonReadiness() {
  var input = document.querySelector('input[name="student_themes"]');
  var addButton = document.getElementById("add-theme");
  var theme = input.value.trim();

  // Check if button can be used (has valid input and not at limit)
  var canSend =
    theme && theme.length >= 3 && theme.length <= 200 && !addButton.disabled;

  if (canSend) {
    startWiggle();
  } else {
    stopWiggle();
  }
}

function startWiggle() {
  var addButton = document.getElementById("add-theme");
  if (!addButton.classList.contains("wiggle")) {
    addButton.classList.add("wiggle");
  }
}

function stopWiggle() {
  var addButton = document.getElementById("add-theme");
  addButton.classList.remove("wiggle");
}

function addTheme() {
  var input = document.querySelector('input[name="student_themes"]');
  var theme = input.value.trim();
  var errorContainer = document.getElementById("form-errors");
  errorContainer.textContent = ""; // очищаємо попередні помилки

  if (theme && theme.length >= 3 && theme.length <= 200) {
    var hiddenThemes = document.getElementById("hidden-themes");
    var themeList = document.getElementById("theme-list");

    // Перевірка на дублікати
    var existingThemes = Array.from(
      hiddenThemes.querySelectorAll('input[name="student_themes"]')
    ).map((input) => input.value.toLowerCase());

    if (existingThemes.includes(theme.toLowerCase())) {
      addErrorElement("Ця тема вже додана!");
      return;
    }

    var hiddenInput = document.createElement("input");
    hiddenInput.type = "hidden";
    hiddenInput.name = "student_themes";
    hiddenInput.value = theme;
    hiddenThemes.appendChild(hiddenInput);

    var listItem = document.createElement("li");
    listItem.className = "theme-item";

    var themeText = document.createElement("span");
    themeText.textContent = theme;
    themeText.title = theme;

    var removeButton = document.createElement("button");
    removeButton.textContent = "×";
    removeButton.className = "remove-theme";
    removeButton.title = "Видалити тему";
    removeButton.addEventListener("click", function () {
      hiddenThemes.removeChild(hiddenInput);
      themeList.removeChild(listItem);
      updateThemeCount();
    });

    listItem.appendChild(themeText);
    listItem.appendChild(removeButton);
    themeList.appendChild(listItem);

    input.value = "";
    updateThemeCount();
    stopWiggle();
  } else if (theme.length > 200) {
    addErrorElement("Тема занадто довга (максимум 200 символів)");
  } else if (theme.length > 0 && theme.length < 3) {
    addErrorElement("Тема повинна містити мінімум 3 символи");
  }
}

// додає помилку у form-errors
function addErrorElement(message) {
  var errorContainer = document.getElementById("form-errors");
  var errorDiv = document.createElement("div");
  errorDiv.className = "error-message";
  errorDiv.textContent = message;
  errorContainer.appendChild(errorDiv);

  setTimeout(() => {
    errorDiv.remove();
  }, 5000);
}

document.querySelector(".close-modal").addEventListener("click", (e) => {
  e.preventDefault();
  document.getElementById("details_request_modal").close();
});

function updateThemeCount() {
  var hiddenThemes = document.getElementById("hidden-themes");
  var themeCount = hiddenThemes.querySelectorAll(
    'input[name="student_themes"]'
  ).length;
  var themeInput = document.getElementById("id_student_themes");
  var addButton = document.getElementById("add-theme");
  var themeCounter = document.getElementById("theme-count");
  var placeholder = document.getElementById("theme-placeholder");
  var themeList = document.getElementById("theme-list");

  // Update counter
  themeCounter.textContent = themeCount;
  themeCounter.parentElement.style.color =
    themeCount >= 3 ? "#dc3545" : "#a3a3a3";

  // Show/hide elements
  if (themeCount > 0) {
    placeholder.style.display = "none";
    themeList.style.display = "block";
  } else {
    placeholder.style.display = "block";
    themeList.style.display = "none";
  }

  // Handle limit reached
  if (themeCount >= 3) {
    addButton.disabled = true;
    themeInput.disabled = true;
    themeInput.placeholder = "Досягнуто ліміт тем (3/3)";
    addButton.style.opacity = "0.5";
    addButton.style.cursor = "not-allowed";
    stopWiggle();
  } else {
    addButton.disabled = false;
    themeInput.disabled = false;
    themeInput.placeholder = "Введіть назву теми...";
    addButton.style.opacity = "1";
    addButton.style.cursor = "pointer";
    checkButtonReadiness();
  }
}

// Initialize theme count on page load
updateThemeCount();

checkButtonReadiness();
