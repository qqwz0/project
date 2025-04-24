from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from apps.catalog.models import Request
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.db import transaction
from .models import Message
from apps.users.models import CustomUser
from django.template.loader import render_to_string
from .utils import send_email_async
from django.urls import reverse
from django.conf import settings
import datetime
import threading
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Request)
def send_notification_on_request(sender, instance, created, **kwargs):
    """Send notification to teacher when a student creates a new request"""
    logger.info(f"Checking if new request was created: {instance.pk}")
    channel_layer = get_channel_layer()
    if created:
        try:
            # Get the teacher's user ID (must be numeric)
            teacher_user_id = instance.teacher_id.pk
            teacher_user = CustomUser.objects.get(id=teacher_user_id)  
            
            student_name = f"{instance.student_id.first_name} {instance.student_id.last_name}"
            student_id = instance.student_id.pk
            
            message = f"Ви отримали запит від студента {student_name}! 📩"
            time = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
            
            notification = f"Новий запит від {student_name}"
            
            profile_url = f"{settings.BASE_URL}{reverse('profile')}"
            student_profile_url = f"{settings.BASE_URL}{reverse('profile_detail', args=[student_id])}"

            
            # Create context with complete URLs
            context = {
                'student_name': student_name,
                'profile_url': profile_url,
                'student_profile_url': student_profile_url,
                'time': time
            }
            

            html_message = render_to_string('notifications/new_request.html', context)
            
            def create_message():
                # Create a new message instance
                Message.objects.create(
                    message_text=message,
                    recipient=teacher_user,
                    sender=instance.student_id,
                    created_at=time,
                )
                event = {
                    "type": "send_notification",
                    "notification": notification,
                    'time': time,
                }
                
                email_thread = threading.Thread(
                 target=send_email_async,
                 args=(
                     f'Новий запит від студента {student_name}',
                     '',
                     'vasylhlova24@gmail.com',
                     [teacher_user.email],
                     html_message
                 )
                )
                email_thread.daemon = True
                email_thread.start()
                     
                # Log the group we're sending to
                group_name = f'user_{teacher_user_id}'
                logger.info(f"Sending notification to teacher group: {group_name}")
                
                # Send to the teacher's group
                async_to_sync(channel_layer.group_send)(group_name, event)
            
            # Use transaction.on_commit to ensure the message is created after the request is saved
            transaction.on_commit(create_message)
        except Exception as e:
            logger.error(f"Failed to send teacher notification: {str(e)}")
        
@receiver(pre_save, sender=Request)
def send_notification_on_request_status_changed(sender, instance,**kwargs):
    """Send notification to student when request status changes"""  
    print("Checking if request status changed")      
    try:
        # Get previous state to check if status changed
        old_instance = sender.objects.get(pk=instance.pk)  
    except sender.DoesNotExist:
        return 
    
    # Only send notification if status actually changed
    if old_instance.request_status != instance.request_status:
        try:
            channel_layer = get_channel_layer()
            
            # Get the student's user ID (must be numeric)
            student_user_id = instance.student_id.pk
            student_user = CustomUser.objects.get(id=student_user_id)
            
            teacher_user = CustomUser.objects.get(id=instance.teacher_id.pk)
            # Create appropriate message based on status
            status_text = "прийняв" if instance.request_status == "accepted" else "відхилив"
            teacher_name = f"{instance.teacher_id} "
            emoji = "✅" if status_text == "прийняв" else "❌"
            message = f"{teacher_name} {status_text} ваш запит! {emoji}"
            rejected_reason = instance.rejected_reason if status_text == "відхилив" else None
            time = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
            
            notification = f"{teacher_name} відповів на ваш запит"
            
            profile_url = f"{settings.BASE_URL}{reverse('profile')}"
            catalog_url = f"{settings.BASE_URL}{reverse('teachers_catalog')}"
            try:
                context = { 
                    'teacher_name': teacher_name,
                    'status_text': status_text,
                    'rejected_reason': rejected_reason,
                    'profile_url': profile_url,
                    'catalog_url': catalog_url,
                    'time': time
                }
                html_message = render_to_string('notifications/status_changed.html', context)
                
                email_thread = threading.Thread(
                    target=send_email_async,
                    args=(
                        f'Увага! Нове повідомлення від викладача {teacher_name}',
                        '',
                        'vasylhlova24@gmail.com',
                        [student_user.email],
                        html_message
                    )
                )
                email_thread.daemon = True
                email_thread.start()
            except Exception as e:
                logger.error(f"Failed to render email template: {str(e)}")
              
            try:
                Message.objects.create(
                    message_text=message,
                    recipient=student_user,
                    sender=teacher_user,
                    created_at=time,
                    status = status_text
                )
            except Exception as e:
                logger.error(f"Failed to create message instance: {str(e)}")
            try:
                event = {
                    "type": "send_notification",
                    "notification": notification,
                    'status': status_text,
                    'rejection_reason': rejected_reason,
                    'time': time
                }
            except Exception as e:
                    logger.error(f"Failed to create event: {str(e)}")
            

            # Log the group we're sending to
            group_name = f"user_{student_user_id}"
            print(f"Sending notification to student group: {group_name}")
            
            # Send to the student's group
            async_to_sync(channel_layer.group_send)(group_name, event)
            
        except Exception as e:
            logger.error(f"Failed to send student notification: {str(e)}")