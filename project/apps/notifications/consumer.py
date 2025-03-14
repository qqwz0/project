from channels.generic.websocket import AsyncWebsocketConsumer
from django.template.loader import get_template
import logging

logger = logging.getLogger(__name__)

class NotificationsConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        
        self.group_name = "notifications"
        
        
        logger.info(f"User connecting to WebSocket")
        
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name  
        )
        
        await self.accept()
        logger.info(f"User connected successfully")
        
    async def disconnect(self, close_code):
        logger.info(f"User disconnecting with code {close_code}")
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
         
    async def send_notification(self, event):
        html = get_template('/notifications/notification.html').render(
            context={'message':event['message']}
        )
        await self.send(text_data=html)


        