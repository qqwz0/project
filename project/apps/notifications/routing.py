from django.urls import path
from .consumer import NotificationsConsumer
from . import consumer

websocket_urlpatterns = [
    path('ws/notifications/', consumer.NotificationsConsumer.as_asgi()),
]