from django.urls import path
from .views import MessageListView, MarkAsReadView

urlpatterns = [
    path('get_messages/', MessageListView.as_view(), name='get_notifications'),
    path('read/<int:message_id>/', MarkAsReadView.as_view(), name='mark_as_read'),  
]