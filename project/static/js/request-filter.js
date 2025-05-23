// Оголошуємо функцію initializeFilters глобально (буде доступна у глобальній області видимості)
window.initializeFilters = function() {
    // Отримуємо всі кнопки фільтрації
    const filterButtons = document.querySelectorAll('.filter-btn');
    
    if (filterButtons.length > 0) {
        // Додаємо обробник кліків для кожної кнопки
        filterButtons.forEach(button => {
            // Видаляємо попередні обробники щоб уникнути дублювання
            button.removeEventListener('click', filterButtonClickHandler);
            // Додаємо новий обробник
            button.addEventListener('click', filterButtonClickHandler);
        });
        
        // Показуємо всі секції за замовчуванням
        const allButton = document.querySelector('.filter-btn[data-filter="all"]');
        if (allButton) {
            // Робимо активною кнопку "Всі"
            filterButtons.forEach(btn => {
                btn.classList.remove('active');
            });
            
            allButton.classList.add('active');
            
            // Фільтруємо запити за значенням "all"
            filterRequests('all');
        }
    }
};

// Функція-обробник для кнопок фільтрації
function filterButtonClickHandler(event) {
    event.preventDefault();
    
    const filter = this.getAttribute('data-filter');
    
    // Знімаємо active клас з усіх кнопок
    const filterButtons = document.querySelectorAll('.filter-btn');
    filterButtons.forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Додаємо active клас до натиснутої кнопки
    this.classList.add('active');
    
    // Додаємо анімацію до кнопки
    this.classList.add('pulse-animation');
    setTimeout(() => {
        this.classList.remove('pulse-animation');
    }, 300);
    
    // Фільтруємо запити
    filterRequests(filter);
}

// Функція фільтрації запитів
function filterRequests(filter) {
    // Знаходимо всі секції запитів
    const sections = document.querySelectorAll('.request-section');
    
    sections.forEach(section => {
        // Застосовуємо логіку фільтрації з анімацією
        if (filter === 'all' || section.classList.contains(filter + '-section')) {
            // Спочатку робимо елемент видимим але прозорим
            section.style.display = 'block';
            section.style.opacity = '0';
            
            // Потім плавно збільшуємо прозорість
            setTimeout(() => {
                section.style.opacity = '1';
                section.style.transition = 'opacity 0.3s ease';
            }, 10);
        } else {
            // Плавно зменшуємо прозорість перед приховуванням
            section.style.opacity = '0';
            section.style.transition = 'opacity 0.3s ease';
            
            // Приховуємо після завершення анімації
            setTimeout(() => {
                section.style.display = 'none';
            }, 300);
        }
    });
}

// Ініціалізуємо фільтри при першому завантаженні сторінки
document.addEventListener('DOMContentLoaded', function() {
    window.initializeFilters();
});

// Додаємо стиль для анімації кнопок
const style = document.createElement('style');
style.textContent = `
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.05); }
        100% { transform: scale(1); }
    }
    
    .pulse-animation {
        animation: pulse 0.3s ease;
    }
    
    .request-section {
        transition: opacity 0.3s ease;
    }
`;
document.head.appendChild(style);

// Допоміжна функція для додавання в лог елементів DOM для відлагодження
function logElementDetails(element) {
    console.log('Element:', element);
    console.log('Class list:', element.classList);
    console.log('Display style:', window.getComputedStyle(element).display);
    console.log('Visibility style:', window.getComputedStyle(element).visibility);
}

function closePopup(element) {
    if (element) {
        element.closest('.success-popup, .error-popup').style.display = 'none';
    } else {
        document.querySelectorAll('.success-popup, .error-popup').forEach(function(popup) {
            popup.style.display = 'none';
        });
    }
}

function showToast(message, type='success') {
    // Видаляємо попередній тост, якщо є
    document.querySelectorAll('.success-popup, .error-popup').forEach(function(popup) {
        popup.remove();
    });
    const toast = document.createElement('div');
    toast.className = `success-popup ${type}`;
    toast.style.position = 'fixed';
    toast.style.top = '20px';
    toast.style.left = '50%';
    toast.style.transform = 'translateX(-50%)';
    toast.style.zIndex = 9999;
    toast.innerHTML = `
        <img src="/static/images/toastIcon.svg" alt="Success" class="success-icon" />
        <div>
            <div class="popup-content">
                <p class="popup-title">${type === 'success' ? 'Успіх!' : 'Помилка!'}</p>
                <p class="popup-text">${message}</p>
            </div>
            <i class="toast-close fas fa-times close" onclick="closePopup(this)"></i>
        </div>
    `;
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.remove();
    }, 3000);
}

window.handleRequest = function(action, requestId) {
    let url;
    if (action === 'approve') {
        url = `/users/approve_request/${requestId}/`;
    } else if (action === 'reject') {
        url = `/users/reject_request/${requestId}/`;
    } else if (action === 'restore') {
        url = `/users/restore_request/${requestId}/`;
    } else {
        alert('Unknown action');
        return;
    }

    fetch(url, {
        method: 'POST',
        headers: {
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(
                action === 'approve' ? 'Запит успішно підтверджено' :
                action === 'reject' ? 'Запит успішно відхилено' :
                action === 'restore' ? 'Запит успішно відновлено' : 'Операція виконана',
                'success'
            );
            // Оновити DOM або перезавантажити частину сторінки, якщо потрібно
            setTimeout(() => { location.reload(); }, 1200);
        } else {
            showToast(data.error || 'Сталася помилка', 'error');
        }
    })
    .catch(error => {
        showToast('Сталася помилка: ' + error, 'error');
    });
}; 