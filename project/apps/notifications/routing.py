from django.urls import path
from .consumer import NotificationsConsumer


websocket_urlpatterns = [
    path('ws/notifications/', NotificationsConsumer.as_asgi()),
]