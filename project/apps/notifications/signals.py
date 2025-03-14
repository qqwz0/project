from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.catalog.models import Request
from channels.layers import get_channel_layer


@receiver(post_save, sender=Request)
def send_notification_on_request(sender, instance, created, **kwargs):
    if created:
        channel_layer = get_channel_layer()
        channel_name = "notifications"
        event = {
            'type': 'send_notification',
            'message': f'New request from {instance.student_id.first_name} {instance.student_id.last_name}'
        }
        channel_layer.group_send(channel_name, event)
        
        