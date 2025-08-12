from django.test import TestCase

import json
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.catalog.models import OnlyTeacher, OnlyStudent, Request, Stream, Slot, TeacherTheme

User = get_user_model()

class TeacherProfileThemeEditTestCase(TestCase):
    def setUp(self):
        """Налаштування тестового середовища для кожного тесту."""
        # Створення користувача-викладача
        self.teacher_user = User.objects.create_user(
            email='teacher.edit@test.com',
            first_name='Викладач',
            last_name='Тестовий',
            role='Викладач',
            department='Системного проектування'
        )
        
        # Створення користувача-студента
        self.student_user = User.objects.create_user(
            email='student.edit@test.com',
            first_name='Студент',
            last_name='Тестовий',
            role='Студент',
            academic_group='ФЕС-21'
        )
        
        # Отримання профілів (сигнали мали б їх створити)
        self.teacher_profile = OnlyTeacher.objects.get(teacher_id=self.teacher_user)
        self.student_profile = OnlyStudent.objects.get_or_create(
            student_id=self.student_user,
            defaults={'course': 2, 'speciality': 'Тестова'}
        )[0]
        
        # Створення потоку та слоту для запитів
        self.stream = Stream.objects.create(
            stream_code='ФЕС-2', specialty_name='Тестова спеціальність'
        )
        self.slot = Slot.objects.create(
            teacher_id=self.teacher_profile, stream_id=self.stream, quota=5
        )
        
        # Створення клієнта та вхід в систему
        self.client = Client()
        self.client.force_login(self.teacher_user)
        
        # URL для редагування
        self.edit_url = reverse('teacher_profile_edit')

    def _get_base_form_data(self):
        """Повертає базовий набір даних для форми профілю."""
        return {
            'first_name': self.teacher_user.first_name,
            'last_name': self.teacher_user.last_name,
            'patronymic': 'Едітович',
            'department': self.teacher_user.department,
            'academic_level': self.teacher_profile.academic_level,
        }

    def test_soft_delete_unused_theme(self):
        """Тест: невикористана тема успішно "м'яко" видаляється."""
        theme_to_delete = TeacherTheme.objects.create(
            teacher_id=self.teacher_profile,
            theme="Тема, яку ніхто не використовує",
            is_deleted=False
        )
        
        data = self._get_base_form_data()
        data['themes_data'] = '[]'  # Порожній список тем для видалення існуючої

        response = self.client.post(self.edit_url, data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        
        theme_to_delete.refresh_from_db()
        self.assertTrue(theme_to_delete.is_deleted)

    def test_prevent_delete_theme_in_active_request(self):
        """Тест: неможливо видалити тему, що використовується в активному запиті."""
        theme_in_use = TeacherTheme.objects.create(
            teacher_id=self.teacher_profile,
            theme="Тема в активному запиті",
            is_deleted=False
        )
        Request.objects.create(
            student_id=self.student_user,
            teacher_id=self.teacher_profile,
            teacher_theme=theme_in_use,
            request_status='Активний',
            slot=self.slot
        )
        
        data = self._get_base_form_data()
        data['themes_data'] = '[]'

        response = self.client.post(self.edit_url, data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        self.assertEqual(response.status_code, 409) # Conflict
        self.assertFalse(response.json()['success'])
        self.assertIn("Неможливо видалити тему", response.json()['message'])
        
        theme_in_use.refresh_from_db()
        self.assertFalse(theme_in_use.is_deleted)

    def test_prevent_delete_theme_in_pending_request(self):
        """Тест: неможливо видалити тему, що використовується в запиті, який очікує."""
        theme_in_use = TeacherTheme.objects.create(
            teacher_id=self.teacher_profile,
            theme="Тема в очікуючому запиті",
            is_deleted=False
        )
        Request.objects.create(
            student_id=self.student_user,
            teacher_id=self.teacher_profile,
            teacher_theme=theme_in_use,
            request_status='Очікує',
            slot=self.slot
        )
        
        data = self._get_base_form_data()
        data['themes_data'] = '[]'

        response = self.client.post(self.edit_url, data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.json()['success'])
        
        theme_in_use.refresh_from_db()
        self.assertFalse(theme_in_use.is_deleted)

    def test_allow_delete_theme_in_completed_request(self):
        """Тест: можна видалити тему, якщо вона є лише в завершеному запиті."""
        theme_completed = TeacherTheme.objects.create(
            teacher_id=self.teacher_profile,
            theme="Тема із завершеного запиту",
            is_deleted=False
        )
        Request.objects.create(
            student_id=self.student_user,
            teacher_id=self.teacher_profile,
            teacher_theme=theme_completed,
            request_status='Завершено',
            slot=self.slot
        )
        
        data = self._get_base_form_data()
        data['themes_data'] = '[]'

        response = self.client.post(self.edit_url, data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        
        theme_completed.refresh_from_db()
        self.assertTrue(theme_completed.is_deleted)

    def test_add_and_delete_themes_simultaneously(self):
        """Тест: одночасне додавання нової теми та видалення старої."""
        theme_to_delete = TeacherTheme.objects.create(
            teacher_id=self.teacher_profile, theme="Стара тема", is_deleted=False
        )
        new_theme_text = "Нова тема"
        
        data = self._get_base_form_data()
        data['themes_data'] = json.dumps([{'theme': new_theme_text, 'description': ''}])

        response = self.client.post(self.edit_url, data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        
        # Перевірка, що стара тема видалена
        theme_to_delete.refresh_from_db()
        self.assertTrue(theme_to_delete.is_deleted)
        
        # Перевірка, що нова тема створена і активна
        self.assertTrue(
            TeacherTheme.objects.filter(
                teacher_id=self.teacher_profile,
                theme=new_theme_text,
                is_deleted=False
            ).exists()
        )
