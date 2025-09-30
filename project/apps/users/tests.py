from django.test import TestCase, TransactionTestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.db import transaction
from apps.catalog.models import OnlyTeacher, OnlyStudentNew, Request, Stream, Slot, TeacherTheme, StudentTheme, Group
from apps.users.forms import StudentProfileForm
from threading import Thread
import time
import json

User = get_user_model()

class StudentGroupValidationTestCase(TestCase):
    def setUp(self):
        # Create test student user
        self.student_user = User.objects.create_user(
            email='student@test.com',
            first_name='Тест',
            last_name='Студент',
            role='Студент',
            academic_group='ФЕС-21'  # Початкова група
        )
        
        # Створюємо тестову групу для тестів
        from apps.catalog.models import Faculty, Specialty
        faculty, _ = Faculty.objects.get_or_create(code='ФЕ', defaults={'name': 'Тестовий факультет'})
        specialty, _ = Specialty.objects.get_or_create(
            code='126', 
            faculty=faculty,
            education_level='bachelor',
            defaults={'name': 'Тестова спеціальність'}
        )
        from apps.catalog.models import Stream
        stream, _ = Stream.objects.get_or_create(
            stream_code='ФЕС-2',
            defaults={'specialty': specialty, 'year_of_entry': 2024}
        )
        test_group, _ = Group.objects.get_or_create(
            group_code='ФЕС-21',
            defaults={'stream': stream}
        )
        
        # Create or get student profile
        self.student_profile, _ = OnlyStudentNew.objects.get_or_create(
            student_id=self.student_user,
            defaults={'group': test_group}
        )

    def test_valid_group_format_saves_correctly(self):
        """Test that valid group format saves without errors"""
        form_data = {
            'first_name': 'Студент',
            'last_name': 'Валідація',
            'patronymic': '',
            'academic_group': 'ФЕС-22',  # Нова коректна група
            'course': 2,
            'education_level': 'bachelor',
            'additional_email': '',
            'phone_number': ''
        }
        
        form = StudentProfileForm(data=form_data, instance=self.student_profile, user=self.student_user)
        
        # Check that form is valid
        if not form.is_valid():
            print(f"Form errors: {form.errors}")
        self.assertTrue(form.is_valid(), f"Form should be valid. Errors: {form.errors}")
        
        # Save the form - this saves only the OnlyStudent instance
        form.save()
        
        # Manual update of user fields (as done in the view)
        self.student_user.academic_group = form.cleaned_data['academic_group']
        self.student_user.save()
        
        # Refresh user from database
        self.student_user.refresh_from_db()
        
        # Check that academic_group was updated
        self.assertEqual(self.student_user.academic_group, 'ФЕС-22')

    def test_invalid_group_format_shows_error(self):
        """Test that invalid group format shows validation error"""
        invalid_groups = [
            'ABC-21',  # not Ukrainian letters  
            'ФЕС21',   # missing dash
            'ФЕС-2',   # incomplete number
            'ФЕС-221', # too long number
            'ФЕХ-21',  # invalid faculty code
            '',        # empty string
        ]
        
        for invalid_group in invalid_groups:
            with self.subTest(group=invalid_group):
                form_data = {
                    'first_name': 'Студент',
                    'last_name': 'Валідація',
                    'patronymic': '',
                    'academic_group': invalid_group,
                    'course': 2,
                    'education_level': 'bachelor',
                    'additional_email': '',
                    'phone_number': ''
                }
                
                form = StudentProfileForm(data=form_data, instance=self.student_profile, user=self.student_user)
                self.assertFalse(form.is_valid(), f"Form should be invalid for group: {invalid_group}")
                self.assertIn('academic_group', form.errors, f"Should have academic_group error for: {invalid_group}")

    def test_lowercase_group_converts_to_uppercase(self):
        """Test that lowercase group letters are converted to uppercase"""
        form_data = {
            'first_name': 'Студент',
            'last_name': 'Валідація',
            'patronymic': '',
            'academic_group': 'фес-22',  # lowercase
            'course': 2,
            'education_level': 'bachelor',
            'additional_email': '',
            'phone_number': ''
        }
        
        form = StudentProfileForm(data=form_data, instance=self.student_profile, user=self.student_user)
        
        # Check that form is valid after conversion
        self.assertTrue(form.is_valid(), f"Form should be valid after uppercase conversion. Errors: {form.errors}")
        
        # Check that academic_group was converted to uppercase
        self.assertEqual(form.cleaned_data['academic_group'], 'ФЕС-22')

    def test_mixed_case_invalid_letters(self):
        """Test that mixed case with invalid letters shows error"""
        invalid_mixed_groups = [
            'abc-21',  # latin letters
            'ФЕХ-21',  # wrong faculty code
            'ФЕС-51',  # invalid course number
            'ФЕ-21',   # incomplete faculty code
        ]
        
        for invalid_group in invalid_mixed_groups:
            with self.subTest(group=invalid_group):
                form_data = {
                    'first_name': 'Студент',
                    'last_name': 'Валідація',
                    'patronymic': '',
                    'academic_group': invalid_group,
                    'course': 2,
                    'education_level': 'bachelor',
                    'additional_email': '',
                    'phone_number': ''
                }
                
                form = StudentProfileForm(data=form_data, instance=self.student_profile, user=self.student_user)
                self.assertFalse(form.is_valid(), f"Form should be invalid for group: {invalid_group}")
                self.assertIn('academic_group', form.errors, f"Should have academic_group error for: {invalid_group}")
    
    def test_course_group_mismatch_shows_error(self):
        """Test that course and group mismatch shows validation error"""
        form_data = {
            'first_name': 'Студент',
            'last_name': 'Валідація',
            'academic_group': 'ФЕС-32',  # Course 3
            'course': 2,  # But course field is 2
            'education_level': 'bachelor'
        }
        
        form = StudentProfileForm(
            data=form_data,
            instance=self.student_profile,
            user=self.student_user
        )
        
        self.assertFalse(form.is_valid())
        self.assertIn('academic_group', form.errors)
        self.assertIn('course', form.errors)
    
    def test_view_displays_validation_errors_ajax(self):
        """Test that view properly returns validation errors for AJAX requests"""
        self.client.force_login(self.student_user)
        
        form_data = {
            'first_name': 'Студент',
            'last_name': 'Валідація',
            'academic_group': 'INVALID',  # Invalid format
            'course': 2,
            'education_level': 'bachelor'
        }
        
        response = self.client.post(
            reverse('student_profile_edit'),
            data=form_data,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertFalse(response_data['success'])
        self.assertIn('errors', response_data)
        self.assertIn('academic_group', response_data['errors'])
    
    def test_view_displays_validation_errors_non_ajax(self):
        """Test that view properly shows validation errors for regular form submissions"""
        self.client.force_login(self.student_user)
        
        form_data = {
            'first_name': 'Студент',
            'last_name': 'Валідація',
            'academic_group': 'INVALID',  # Invalid format
            'course': 2,
            'education_level': 'bachelor'
        }
        
        response = self.client.post(
            reverse('student_profile_edit'),
            data=form_data
        )
        
        # Should render form again with errors
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Помилка при збереженні профілю')
        self.assertContains(response, 'INVALID')


class RequestApprovalTestCase(TransactionTestCase):
    def setUp(self):
        # Create test users
        self.teacher_user = User.objects.create_user(
            email='teacher@test.com',
            first_name='Викладач',
            last_name='Тестовий',
            role='Викладач',
            department='Системного проектування'
        )
        
        self.student_user = User.objects.create_user(
            email='student@test.com',
            first_name='Студент',
            last_name='Тестовий',
            role='Студент',
            academic_group='ФЕС-21'
        )
        
        # Get or create profiles (signal might have already created them)
        self.teacher_profile, _ = OnlyTeacher.objects.get_or_create(
            teacher_id=self.teacher_user,
            defaults={'academic_level': 'Доцент'}
        )
        
        self.student_profile, _ = OnlyStudentNew.objects.get_or_create(
            student_id=self.student_user,
            defaults={
                'course': 2,
                'speciality': 'Тестова'
            }
        )
        
        # Create stream and slot
        self.stream, _ = Stream.objects.get_or_create(
            stream_code='ФЕС-2',
            defaults={'specialty_name': 'Тестова спеціальність'}
        )
        
        self.slot, _ = Slot.objects.get_or_create(
            teacher_id=self.teacher_profile,
            stream_id=self.stream,
            defaults={
                'quota': 3,
                'occupied': 0
            }
        )
    
    def test_single_accept_cancels_other_pending(self):
        """Test that accepting one request cancels all other pending requests from the same student"""
        
        # Create multiple pending requests for the same student
        request1 = Request.objects.create(
            student_id=self.student_user,
            teacher_id=self.teacher_profile,
            slot=self.slot,
            request_status='Очікує',
            motivation_text='Request 1'
        )
        
        request2 = Request.objects.create(
            student_id=self.student_user,
            teacher_id=self.teacher_profile,
            slot=self.slot,
            request_status='Очікує',
            motivation_text='Request 2'
        )
        
        request3 = Request.objects.create(
            student_id=self.student_user,
            teacher_id=self.teacher_profile,
            slot=self.slot,
            request_status='Очікує',
            motivation_text='Request 3'
        )
        
        # Login as teacher
        self.client.force_login(self.teacher_user)
        
        # Approve the first request
        url = reverse('approve_request', kwargs={'request_id': request1.id})
        response = self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        
        # Refresh from database
        request1.refresh_from_db()
        request2.refresh_from_db()
        request3.refresh_from_db()
        
        # Check that request1 is accepted
        self.assertEqual(request1.request_status, 'Активний')
        
        # Check that other requests are cancelled
        self.assertEqual(request2.request_status, 'Відхилено')
        self.assertEqual(request3.request_status, 'Відхилено')
        
        # Check the reason for cancellation
        self.assertIn('Автоматично скасовано', request2.rejected_reason)
        self.assertIn('Автоматично скасовано', request3.rejected_reason)
    
    def test_concurrent_approval_only_one_accepted(self):
        """Test that concurrent approval requests result in only one acceptance"""
        
        # Create two pending requests
        request1 = Request.objects.create(
            student_id=self.student_user,
            teacher_id=self.teacher_profile,
            slot=self.slot,
            request_status='Очікує',
            motivation_text='Request 1'
        )
        
        request2 = Request.objects.create(
            student_id=self.student_user,
            teacher_id=self.teacher_profile,
            slot=self.slot,
            request_status='Очікує',
            motivation_text='Request 2'
        )
        
        results = []
        
        def approve_request(request_id):
            """Helper function to approve a request in a separate thread"""
            from django.test import Client
            client = Client()
            client.force_login(self.teacher_user)
            url = reverse('approve_request', kwargs={'request_id': request_id})
            try:
                response = client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
                results.append((request_id, response.status_code))
            except Exception as e:
                results.append((request_id, str(e)))
        
        # Start two threads to approve requests simultaneously
        thread1 = Thread(target=approve_request, args=(request1.id,))
        thread2 = Thread(target=approve_request, args=(request2.id,))
        
        thread1.start()
        thread2.start()
        
        thread1.join()
        thread2.join()
        
        # Refresh from database
        request1.refresh_from_db()
        request2.refresh_from_db()
        
        # Count active requests
        active_count = Request.objects.filter(
            student_id=self.student_user,
            request_status='Активний'
        ).count()
        
        # Only one should be active
        self.assertEqual(active_count, 1)
        
        # One should be active, one should be cancelled
        statuses = {request1.request_status, request2.request_status}
        self.assertIn('Активний', statuses)
        self.assertIn('Відхилено', statuses)

    def test_approve_request_with_theme_cancels_others(self):
        """Test that approve_request_with_theme also cancels other pending requests"""
        
        # Create teacher theme
        teacher_theme = TeacherTheme.objects.create(
            teacher_id=self.teacher_profile,
            theme='Тестова тема',
            theme_description='Опис тестової теми',
            is_occupied=False
        )
        
        # Create multiple pending requests for the same student
        request1 = Request.objects.create(
            student_id=self.student_user,
            teacher_id=self.teacher_profile,
            slot=self.slot,
            request_status='Очікує',
            motivation_text='Request 1'
        )
        
        request2 = Request.objects.create(
            student_id=self.student_user,
            teacher_id=self.teacher_profile,
            slot=self.slot,
            request_status='Очікує',
            motivation_text='Request 2'
        )
        
        # Login as teacher
        self.client.force_login(self.teacher_user)
        
        # Approve the first request with theme
        url = reverse('approve_request_with_theme', kwargs={'request_id': request1.id})
        data = {
            'theme_id': f'teacher_{teacher_theme.id}',
            'comment': 'Test comment',
            'send_contacts': True
        }
        
        response = self.client.post(
            url, 
            data=json.dumps(data), 
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data['success'])
        
        # Refresh from database
        request1.refresh_from_db()
        request2.refresh_from_db()
        
        # Check that request1 is accepted
        self.assertEqual(request1.request_status, 'Активний')
        
        # Check that other request is cancelled
        self.assertEqual(request2.request_status, 'Відхилено')
        self.assertIn('Автоматично скасовано', request2.rejected_reason)

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
        self.student_profile = OnlyStudentNew.objects.get_or_create(
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
            'department': self.teacher_user.get_department_name(),
            'academic_level': self.teacher_profile.academic_level,
        }

    def test_delete_unused_theme(self):
        """Тест: невикористана тема успішно видаляється."""
        theme_to_delete = TeacherTheme.objects.create(
            teacher_id=self.teacher_profile,
            theme="Тема, яку ніхто не використовує",
        )
        
        data = self._get_base_form_data()
        data['themes_data'] = '[]'  # Порожній список тем для видалення існуючої

        response = self.client.post(self.edit_url, data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        
        self.assertFalse(TeacherTheme.objects.filter(id=theme_to_delete.id).exists())

    def test_prevent_delete_theme_in_active_request(self):
        """Тест: неможливо видалити тему, що використовується в активному запиті."""
        theme_in_use = TeacherTheme.objects.create(
            teacher_id=self.teacher_profile,
            theme="Тема в активному запиті",
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
        
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])
        self.assertIn("Неможливо видалити тему", response.json()['message'])
        
        self.assertTrue(TeacherTheme.objects.filter(id=theme_in_use.id).exists())

    def test_prevent_delete_theme_in_pending_request(self):
        """Тест: неможливо видалити тему, що використовується в запиті, який очікує."""
        theme_in_use = TeacherTheme.objects.create(
            teacher_id=self.teacher_profile,
            theme="Тема в очікуючому запиті",
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
        
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])
        
        self.assertTrue(TeacherTheme.objects.filter(id=theme_in_use.id).exists())

    def test_allow_delete_theme_in_completed_request(self):
        """Тест: можна видалити тему, якщо вона є лише в завершеному запиті."""
        theme_completed = TeacherTheme.objects.create(
            teacher_id=self.teacher_profile,
            theme="Тема із завершеного запиту",
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
        
        self.assertFalse(TeacherTheme.objects.filter(id=theme_completed.id).exists())

    def test_add_and_delete_themes_simultaneously(self):
        """Тест: одночасне додавання нової теми та видалення старої."""
        theme_to_delete = TeacherTheme.objects.create(
            teacher_id=self.teacher_profile, theme="Стара тема"
        )
        new_theme_text = "Нова тема"
        
        data = self._get_base_form_data()
        data['themes_data'] = json.dumps([{'theme': new_theme_text, 'description': ''}])

        response = self.client.post(self.edit_url, data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        
        # Перевірка, що стара тема видалена
        self.assertFalse(TeacherTheme.objects.filter(id=theme_to_delete.id).exists())
        
        # Перевірка, що нова тема створена
        self.assertTrue(
            TeacherTheme.objects.filter(
                teacher_id=self.teacher_profile,
                theme=new_theme_text,
            ).exists()
        )
