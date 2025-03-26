from channels.generic.websocket import AsyncWebsocketConsumer
from django.template.loader import get_template
import logging

logger = logging.getLogger(__name__)

class NotificationsConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        if self.user.is_authenticated:
            self.group_name = f'user_{self.user.id}'
            logger.info(f"User {self.user.id} connecting to group {self.group_name}")
            
            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name
            )
            await self.accept() 
            logger.info(f"User connected successfully")
        else:
            logger.warning(f"Unauthenticated connection attempt rejected")
            await self.close()
        
    async def disconnect(self, close_code):
        logger.info(f"User disconnecting with code {close_code}")
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
         
    async def send_notification(self, event):
        # Choose template based on notification type if provided
        template_name = 'notifications/notification.html'
        context = {
            'message': event['message'],
            'time': event['time'] 
        }
        
        # Add additional context if available
        if 'status' in event:
            context['status'] = event['status']
        
        # Render appropriate template
        html = get_template(template_name).render(context)
        await self.send(text_data=html)


        