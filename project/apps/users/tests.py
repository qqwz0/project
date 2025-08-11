from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.db import transaction
from apps.catalog.models import OnlyTeacher, OnlyStudent, Request, Stream, Slot, TeacherTheme
from threading import Thread
import time

User = get_user_model()

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
