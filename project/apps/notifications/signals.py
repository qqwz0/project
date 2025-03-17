from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from apps.catalog.models import Request
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
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
            
            student_name = f"{instance.student_id.first_name} {instance.student_id.last_name}"
            message = f"Новий запит від студента {student_name}"
            
            # Create the notification event
            event = {
                "type": "send_notification",
                "message": message
            }
            
            # Log the group we're sending to
            group_name = f'user_{teacher_user_id}'
            logger.info(f"Sending notification to teacher group: {group_name}")
            
            # Send to the teacher's group
            async_to_sync(channel_layer.group_send)(group_name, event)
            
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
    if old_instance.requset_status != instance.request_status:
        try:
            channel_layer = get_channel_layer()
            
            # Get the student's user ID (must be numeric)
            student_user_id = instance.student_id.user.id
            
            # Create appropriate message based on status
            status_text = "прийнято" if instance.request_status == "accepted" else "відхилено"
            teacher_name = f"{instance.teacher_id.last_name} {instance.teacher_id.first_name}"
            message = f"Ваш запит до викладача {teacher_name} було {status_text}"
            
            # Create the notification event
            event = {
                "type": "send_notification",
                "message": message,
                'status': status_text
            }
            
            # Log the group we're sending to
            group_name = f"user_{student_user_id}"
            print(f"Sending notification to student group: {group_name}")
            
            # Send to the student's group
            async_to_sync(channel_layer.group_send)(group_name, event)
            
        except Exception as e:
            logger.error(f"Failed to send student notification: {str(e)}")