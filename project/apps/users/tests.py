from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.db import transaction
from apps.catalog.models import OnlyTeacher, OnlyStudent, Request, Stream, Slot, TeacherTheme
from apps.users.forms import StudentProfileForm
from threading import Thread
import time
import json

User = get_user_model()

class StudentGroupValidationTestCase(TestCase):
    def setUp(self):
        # Create test student user
        self.student_user = User.objects.create_user(
            email='student.validation@test.com',
            first_name='Студент',
            last_name='Валідація',
            role='Студент',
            academic_group='ФЕС-21'  # Початкова група
        )
        
        # Create or get student profile
        self.student_profile, _ = OnlyStudent.objects.get_or_create(
            student_id=self.student_user,
            defaults={
                'course': 2,
                'speciality': 'Тестова спеціальність'
            }
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
        self.assertIn('error', response_data)
        self.assertNotIn('success', response_data)  # При помилці success не повертається
        self.assertIn('використовується', response_data['error'])
    
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
        self.assertContains(response, 'error-message')
        
        # Check that original values are preserved in case of error
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
        
        self.student_profile, _ = OnlyStudent.objects.get_or_create(
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
        response = self.client.post(url)
        
        # Check response
        self.assertEqual(response.status_code, 302)  # Redirect
        
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
                response = client.post(url)
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
            data=data, 
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data['success'])
        self.assertEqual(response_data['cancelled_count'], 1)
        
        # Refresh from database
        request1.refresh_from_db()
        request2.refresh_from_db()
        
        # Check that request1 is accepted
        self.assertEqual(request1.request_status, 'Активний')
        
        # Check that other request is cancelled
        self.assertEqual(request2.request_status, 'Відхилено')
        self.assertIn('Автоматично скасовано', request2.rejected_reason)

class TeacherThemeCRUDTestCase(TestCase):
    def setUp(self):
        # Створюємо викладача
        self.teacher_user = User.objects.create_user(
            email='teacher.crud@test.com',
            first_name='Викладач',
            last_name='CRUD',
            role='Викладач',
            department='Системного проектування'
        )
        self.teacher_profile, _ = OnlyTeacher.objects.get_or_create(
            teacher_id=self.teacher_user,
            defaults={'academic_level': 'Доцент'}
        )
        
        # Створюємо потоки для тестування
        self.stream1 = Stream.objects.create(
            specialty_name='Комп\'ютерні науки',
            stream_code='ФЕС-2'
        )
        self.stream2 = Stream.objects.create(
            specialty_name='Інформаційні технології',
            stream_code='ФЕІ-3'
        )
        
        # Створюємо тему для тестування
        self.theme = TeacherTheme.objects.create(
            teacher_id=self.teacher_profile,
            theme='Тест тема',
            theme_description='Опис тест теми',
            is_active=True
        )
        
    def test_theme_deactivation(self):
        """Тест деактивації теми"""
        self.assertTrue(self.theme.is_active)
        self.theme.deactivate()
        self.assertFalse(self.theme.is_active)
        
    def test_theme_activation(self):
        """Тест активації теми"""
        self.theme.is_active = False
        self.theme.save()
        self.assertFalse(self.theme.is_active)
        self.theme.activate()
        self.assertTrue(self.theme.is_active)
        
    def test_attach_theme_to_streams(self):
        """Тест прикріплення теми до потоків"""
        self.theme.streams.set([self.stream1, self.stream2])
        attached_streams = list(self.theme.streams.all())
        self.assertEqual(len(attached_streams), 2)
        self.assertIn(self.stream1, attached_streams)
        self.assertIn(self.stream2, attached_streams)
        
    def test_detach_theme_from_streams(self):
        """Тест відкріплення теми від потоків"""
        self.theme.streams.set([self.stream1, self.stream2])
        self.assertEqual(self.theme.streams.count(), 2)
        
        self.theme.streams.clear()
        self.assertEqual(self.theme.streams.count(), 0)
        
    def test_can_be_deleted_without_requests(self):
        """Тест перевірки можливості видалення теми без запитів"""
        self.assertTrue(self.theme.can_be_deleted())
        
    def test_cannot_be_deleted_with_active_requests(self):
        """Тест перевірки неможливості видалення теми з активними запитами"""
        # Створюємо студента
        student_user = User.objects.create_user(
            email='student.theme@test.com',
            first_name='Студент',
            last_name='Тест',
            role='Студент',
            academic_group='ФЕС-21'
        )
        student_profile, _ = OnlyStudent.objects.get_or_create(
            student_id=student_user,
            defaults={'course': 2, 'speciality': 'Тестова спеціальність'}
        )
        
        # Створюємо слот
        slot = Slot.objects.create(
            teacher_id=self.teacher_profile,
            stream_id=self.stream1,
            quota=5,
            occupied=0
        )
        
        # Створюємо активний запит з цією темою
        request = Request.objects.create(
            student_id=student_user,
            teacher_id=self.teacher_profile,
            slot=slot,
            teacher_theme=self.theme,
            motivation_text='Тест мотивація',
            request_status='Активний'
        )
        
        self.assertFalse(self.theme.can_be_deleted())
        
    def test_get_active_themes_filter(self):
        """Тест фільтрації активних тем"""
        # Створюємо неактивну тему
        inactive_theme = TeacherTheme.objects.create(
            teacher_id=self.teacher_profile,
            theme='Неактивна тема',
            theme_description='Опис неактивної теми',
            is_active=False
        )
        
        active_themes = TeacherTheme.get_active_themes()
        self.assertIn(self.theme, active_themes)
        self.assertNotIn(inactive_theme, active_themes)
        
    def test_get_available_themes_filter(self):
        """Тест фільтрації доступних тем"""
        # Створюємо зайняту тему
        occupied_theme = TeacherTheme.objects.create(
            teacher_id=self.teacher_profile,
            theme='Зайнята тема',
            theme_description='Опис зайнятої теми',
            is_active=True,
            is_occupied=True
        )
        
        available_themes = TeacherTheme.get_available_themes(self.teacher_profile)
        self.assertIn(self.theme, available_themes)
        self.assertNotIn(occupied_theme, available_themes)
        
    def test_theme_str_method_with_status(self):
        """Тест відображення статусу теми в __str__"""
        active_str = str(self.theme)
        self.assertIn('🟢', active_str)
        
        self.theme.is_active = False
        self.theme.save()
        inactive_str = str(self.theme)
        self.assertIn('🔴', inactive_str)

class TeacherThemeAPITestCase(TestCase):
    def setUp(self):
        # Створюємо викладача
        self.teacher_user = User.objects.create_user(
            email='teacher.api@test.com',
            first_name='Викладач',
            last_name='API',
            role='Викладач',
            department='Системного проектування'
        )
        self.teacher_profile, _ = OnlyTeacher.objects.get_or_create(
            teacher_id=self.teacher_user,
            defaults={'academic_level': 'Доцент'}
        )
        
        # Створюємо іншого викладача для тестування прав доступу
        self.other_teacher_user = User.objects.create_user(
            email='other.teacher@test.com',
            first_name='Інший',
            last_name='Викладач',
            role='Викладач',
            department='Інша кафедра'
        )
        self.other_teacher_profile, _ = OnlyTeacher.objects.get_or_create(
            teacher_id=self.other_teacher_user,
            defaults={'academic_level': 'Асистент'}
        )
        
        # Створюємо потоки
        self.stream1 = Stream.objects.create(
            specialty_name='Комп\'ютерні науки',
            stream_code='ФЕС-2'
        )
        self.stream2 = Stream.objects.create(
            specialty_name='Інформаційні технології',
            stream_code='ФЕІ-3'
        )
        
        # Створюємо тему
        self.theme = TeacherTheme.objects.create(
            teacher_id=self.teacher_profile,
            theme='API тест тема',
            theme_description='Опис API тест теми',
            is_active=True
        )
        
    def test_deactivate_theme_success(self):
        """Тест успішної деактивації теми через API"""
        self.client.force_login(self.teacher_user)
        response = self.client.post(
            reverse('deactivate_teacher_theme', kwargs={'theme_id': self.theme.id}),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        
        # Перевіряємо, що тема деактивована
        self.theme.refresh_from_db()
        self.assertFalse(self.theme.is_active)
        
    def test_activate_theme_success(self):
        """Тест успішної активації теми через API"""
        self.theme.is_active = False
        self.theme.save()
        
        self.client.force_login(self.teacher_user)
        response = self.client.post(
            reverse('activate_teacher_theme', kwargs={'theme_id': self.theme.id}),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        
        # Перевіряємо, що тема активована
        self.theme.refresh_from_db()
        self.assertTrue(self.theme.is_active)
        
    def test_delete_theme_success(self):
        """Тест успішного видалення теми через API"""
        self.client.force_login(self.teacher_user)
        theme_id = self.theme.id
        
        response = self.client.post(
            reverse('delete_teacher_theme', kwargs={'theme_id': theme_id}),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        
        # Перевіряємо, що тема видалена
        self.assertFalse(TeacherTheme.objects.filter(id=theme_id).exists())
        
    def test_delete_theme_with_active_requests_fails(self):
        """Тест неможливості видалення теми з активними запитами"""
        # Створюємо студента та запит
        student_user = User.objects.create_user(
            email='student.api@test.com',
            first_name='Студент',
            last_name='API',
            role='Студент',
            academic_group='ФЕС-21'
        )
        student_profile, _ = OnlyStudent.objects.get_or_create(
            student_id=student_user,
            defaults={'course': 2, 'speciality': 'Тестова спеціальність'}
        )
        
        slot = Slot.objects.create(
            teacher_id=self.teacher_profile,
            stream_id=self.stream1,
            quota=5,
            occupied=0
        )
        
        Request.objects.create(
            student_id=student_user,
            teacher_id=self.teacher_profile,
            slot=slot,
            teacher_theme=self.theme,
            motivation_text='Тест',
            request_status='Активний'
        )
        
        self.client.force_login(self.teacher_user)
        response = self.client.post(
            reverse('delete_teacher_theme', kwargs={'theme_id': self.theme.id}),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertIn('error', response_data)
        self.assertNotIn('success', response_data)  # При помилці success не повертається
        self.assertIn('використовується', response_data['error'])
        
    def test_attach_theme_to_streams_success(self):
        """Тест успішного прикріплення теми до потоків"""
        self.client.force_login(self.teacher_user)
        response = self.client.post(
            reverse('attach_theme_to_streams', kwargs={'theme_id': self.theme.id}),
            data=json.dumps({'stream_ids': [self.stream1.id, self.stream2.id]}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        
        # Перевіряємо, що потоки прикріплені
        self.theme.refresh_from_db()
        attached_streams = list(self.theme.streams.all())
        self.assertEqual(len(attached_streams), 2)
        self.assertIn(self.stream1, attached_streams)
        self.assertIn(self.stream2, attached_streams)
        
    def test_detach_theme_from_streams(self):
        """Тест відкріплення теми від потоків"""
        # Спочатку прикріплюємо потоки
        self.theme.streams.set([self.stream1, self.stream2])
        
        self.client.force_login(self.teacher_user)
        response = self.client.post(
            reverse('attach_theme_to_streams', kwargs={'theme_id': self.theme.id}),
            data=json.dumps({'stream_ids': []}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        
        # Перевіряємо, що потоки відкріплені
        self.theme.refresh_from_db()
        self.assertEqual(self.theme.streams.count(), 0)
        
    def test_unauthorized_access_fails(self):
        """Тест відмови доступу для чужих тем"""
        self.client.force_login(self.other_teacher_user)
        
        # Тестуємо всі операції
        operations = [
            ('deactivate_teacher_theme', self.theme.id),
            ('activate_teacher_theme', self.theme.id),
            ('delete_teacher_theme', self.theme.id),
            ('attach_theme_to_streams', self.theme.id),
        ]
        
        for url_name, theme_id in operations:
            with self.subTest(operation=url_name):
                response = self.client.post(
                    reverse(url_name, kwargs={'theme_id': theme_id}),
                    HTTP_X_REQUESTED_WITH='XMLHttpRequest'
                )
                self.assertEqual(response.status_code, 403)
                self.assertIn('немає прав', response.json().get('error', ''))
                
    def test_update_theme_success(self):
        """Тест успішного оновлення теми"""
        self.client.force_login(self.teacher_user)
        
        data = {
            'theme': 'Оновлена назва теми',
            'description': 'Оновлений опис теми'
        }
        
        response = self.client.post(
            reverse('update_teacher_theme', kwargs={'theme_id': self.theme.id}),
            data=json.dumps(data),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data['success'])
        self.assertIn('успішно оновлено', response_data['message'])
        
        # Перевіряємо що тема дійсно оновилася
        self.theme.refresh_from_db()
        self.assertEqual(self.theme.theme, 'Оновлена назва теми')
        self.assertEqual(self.theme.theme_description, 'Оновлений опис теми')
        
    def test_update_theme_empty_name_fails(self):
        """Тест що порожня назва теми не дозволена"""
        self.client.force_login(self.teacher_user)
        
        data = {
            'theme': '',
            'description': 'Опис'
        }
        
        response = self.client.post(
            reverse('update_teacher_theme', kwargs={'theme_id': self.theme.id}),
            data=json.dumps(data),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertIn('error', response_data)
        self.assertIn('порожньою', response_data['error'])
        
    def test_update_theme_duplicate_name_fails(self):
        """Тест що дублікати назв тем не дозволені"""
        # Створюємо другу тему
        theme2 = TeacherTheme.objects.create(
            teacher_id=self.teacher_profile,
            theme='Друга тема',
            theme_description='Опис другої теми',
            is_active=True
        )
        
        self.client.force_login(self.teacher_user)
        
        data = {
            'theme': theme2.theme,  # Використовуємо назву іншої теми
            'description': 'Новий опис'
        }
        
        response = self.client.post(
            reverse('update_teacher_theme', kwargs={'theme_id': self.theme.id}),
            data=json.dumps(data),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertIn('error', response_data)
        self.assertIn('вже є тема з такою назвою', response_data['error'])
        
    def test_update_theme_unauthorized_fails(self):
        """Тест що інший викладач не може редагувати чужі теми"""
        self.client.force_login(self.other_teacher_user)
        
        data = {
            'theme': 'Хакерська тема',
            'description': 'Спроба зламати'
        }
        
        response = self.client.post(
            reverse('update_teacher_theme', kwargs={'theme_id': self.theme.id}),
            data=json.dumps(data),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 403)
        response_data = response.json()
        self.assertIn('error', response_data)
        self.assertIn('прав для редагування', response_data['error'])
